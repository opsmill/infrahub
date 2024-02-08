from typing import List

from pydantic import BaseModel

from infrahub import lock
from infrahub.core.constants import CheckType, DiffAction, InfrahubKind, ProposedChangeState
from infrahub.core.integrity.object_conflict.conflict_recorder import ObjectConflictValidatorRecorder
from infrahub.core.manager import NodeManager
from infrahub.core.registry import registry
from infrahub.core.validators.uniqueness.checker import UniquenessChecker
from infrahub.git.repository import InfrahubRepository
from infrahub.log import get_logger
from infrahub.message_bus import InfrahubMessage, messages
from infrahub.message_bus.types import ProposedChangeBranchDiff, ProposedChangeRepository
from infrahub.services import InfrahubServices

log = get_logger()


async def cancel(message: messages.RequestProposedChangeCancel, service: InfrahubServices) -> None:
    """Cancel a proposed change."""
    log.info("Cancelling proposed change", id=message.proposed_change)
    proposed_change = await service.client.get(kind=InfrahubKind.PROPOSEDCHANGE, id=message.proposed_change)
    proposed_change.state.value = ProposedChangeState.CANCELED.value
    await proposed_change.save()


async def data_integrity(message: messages.RequestProposedChangeDataIntegrity, service: InfrahubServices) -> None:
    """Triggers a data integrity validation check on the provided proposed change to start."""
    log.info(f"Got a request to process data integrity defined in proposed_change: {message.proposed_change}")

    proposed_change = await NodeManager.get_one_by_id_or_default_filter(
        id=message.proposed_change, schema_name=InfrahubKind.PROPOSEDCHANGE, db=service.database
    )
    source_branch = await registry.get_branch(db=service.database, branch=proposed_change.source_branch.value)
    diff = await source_branch.diff(db=service.database, branch_only=False)
    conflicts = await diff.get_conflicts_graph(db=service.database)

    async with service.database.start_transaction() as db:
        object_conflict_validator_recorder = ObjectConflictValidatorRecorder(
            db=db,
            validator_kind=InfrahubKind.DATAVALIDATOR,
            validator_label="Data Integrity",
            check_schema_kind=InfrahubKind.DATACHECK,
        )
        await object_conflict_validator_recorder.record_conflicts(message.proposed_change, conflicts)


async def pipeline(message: messages.RequestProposedChangePipeline, service: InfrahubServices) -> None:
    service.log.info("Starting pipeline", propoced_change=message.proposed_change)
    events: list[InfrahubMessage] = []

    repositories = await _get_proposed_change_repositories(message=message, service=service)
    if not message.source_branch_data_only and await _validate_repository_merge_conflicts(repositories=repositories):
        for repo in repositories:
            if not repo.read_only:
                events.append(
                    messages.RequestRepositoryChecks(
                        proposed_change=message.proposed_change,
                        repository=repo.repository_id,
                        source_branch=repo.source_branch,
                        target_branch=repo.destination_branch,
                    )
                )
        for event in events:
            event.assign_meta(parent=message)
            await service.send(message=event)
        service.log.info("Pipeline aborted due to merge conflicts", propoced_change=message.proposed_change)
        return

    await _gather_repository_repository_diffs(repositories=repositories)

    diff_summary = await service.client.get_diff_summary(branch=message.source_branch)
    branch_diff = ProposedChangeBranchDiff(diff_summary=diff_summary, repositories=repositories)

    if message.check_type in [CheckType.ALL, CheckType.ARTIFACT]:
        events.append(
            messages.RequestProposedChangeRefreshArtifacts(
                proposed_change=message.proposed_change,
                source_branch=message.source_branch,
                source_branch_data_only=message.source_branch_data_only,
                destination_branch=message.destination_branch,
                branch_diff=branch_diff,
            )
        )

    if message.check_type in [CheckType.ALL, CheckType.DATA] and branch_diff.has_node_changes(
        branch=message.source_branch
    ):
        events.append(
            messages.RequestProposedChangeDataIntegrity(
                proposed_change=message.proposed_change,
                source_branch=message.source_branch,
                source_branch_data_only=message.source_branch_data_only,
                destination_branch=message.destination_branch,
                branch_diff=branch_diff,
            )
        )

    if message.check_type in [CheckType.ALL, CheckType.REPOSITORY, CheckType.USER]:
        events.append(
            messages.RequestProposedChangeRepositoryChecks(
                proposed_change=message.proposed_change,
                source_branch=message.source_branch,
                source_branch_data_only=message.source_branch_data_only,
                destination_branch=message.destination_branch,
                branch_diff=branch_diff,
            )
        )

    if message.check_type in [CheckType.ALL, CheckType.SCHEMA] and branch_diff.has_data_changes(
        branch=message.source_branch
    ):
        events.append(
            messages.RequestProposedChangeSchemaIntegrity(
                proposed_change=message.proposed_change,
                source_branch=message.source_branch,
                source_branch_data_only=message.source_branch_data_only,
                destination_branch=message.destination_branch,
                branch_diff=branch_diff,
            )
        )

    for event in events:
        event.assign_meta(parent=message)
        await service.send(message=event)


async def schema_integrity(
    message: messages.RequestProposedChangeSchemaIntegrity,
    service: InfrahubServices,  # pylint: disable=unused-argument
) -> None:
    log.info(f"Got a request to process schema integrity defined in proposed_change: {message.proposed_change}")
    proposed_change = await NodeManager.get_one_by_id_or_default_filter(
        id=message.proposed_change, schema_name=InfrahubKind.PROPOSEDCHANGE, db=service.database
    )

    altered_schema_kinds = set()
    for node_diff in message.branch_diff.diff_summary:
        if node_diff["branch"] == proposed_change.source_branch.value and {DiffAction.ADDED, DiffAction.UPDATED} & set(
            node_diff["actions"]
        ):
            altered_schema_kinds.add(node_diff["kind"])

    uniqueness_checker = UniquenessChecker(db=service.database)
    uniqueness_conflicts = await uniqueness_checker.get_conflicts(
        schemas=altered_schema_kinds,
        source_branch=proposed_change.source_branch.value,
    )

    async with service.database.start_transaction() as db:
        object_conflict_validator_recorder = ObjectConflictValidatorRecorder(
            db=db,
            validator_kind=InfrahubKind.SCHEMAVALIDATOR,
            validator_label="Schema Integrity",
            check_schema_kind=InfrahubKind.SCHEMACHECK,
        )
        await object_conflict_validator_recorder.record_conflicts(message.proposed_change, uniqueness_conflicts)


async def repository_checks(message: messages.RequestProposedChangeRepositoryChecks, service: InfrahubServices) -> None:
    log.info(f"Got a request to process checks defined in proposed_change: {message.proposed_change}")

    events: List[InfrahubMessage] = []
    for repository in message.branch_diff.repositories:
        if not message.source_branch_data_only and not repository.read_only:
            events.append(
                messages.RequestRepositoryChecks(
                    proposed_change=message.proposed_change,
                    repository=repository.repository_id,
                    source_branch=message.source_branch,
                    target_branch=message.destination_branch,
                )
            )
        events.append(
            messages.RequestRepositoryUserChecks(
                proposed_change=message.proposed_change,
                repository=repository.repository_id,
                source_branch=message.source_branch,
                target_branch=message.destination_branch,
            )
        )
    for event in events:
        event.assign_meta(parent=message)
        await service.send(message=event)


async def refresh_artifacts(message: messages.RequestProposedChangeRefreshArtifacts, service: InfrahubServices) -> None:
    log.info(f"Refreshing artifacts for change_proposal={message.proposed_change}")
    proposed_change = await service.client.get(kind=InfrahubKind.PROPOSEDCHANGE, id=message.proposed_change)
    artifact_definitions = await service.client.all(
        kind=InfrahubKind.ARTIFACTDEFINITION, branch=proposed_change.source_branch.value
    )
    for artifact_definition in artifact_definitions:
        msg = messages.RequestArtifactDefinitionCheck(
            artifact_definition=artifact_definition.id,
            proposed_change=message.proposed_change,
            source_branch=proposed_change.source_branch.value,
            target_branch=proposed_change.destination_branch.value,
        )

        msg.assign_meta(parent=message)
        await service.send(message=msg)


DESTINATION_ALLREPOSITORIES = """
query DestinationBranchRepositories {
  CoreGenericRepository {
    edges {
      node {
        __typename
        id
        name {
          value
        }
        ... on CoreRepository {
          commit {
            value
          }
        }
        ... on CoreReadOnlyRepository {
          commit {
            value
          }
        }
      }
    }
  }
}
"""

SOURCE_REPOSITORIES = """
query MyQuery {
  CoreRepository {
    edges {
      node {
        __typename
        id
        name {
          value
        }
        commit {
          value
        }
      }
    }
  }
}
"""
SOURCE_READONLY_REPOSITORIES = """
query MyQuery {
  CoreReadOnlyRepository {
    edges {
      node {
        __typename
        id
        name {
          value
        }
        commit {
          value
        }
      }
    }
  }
}
"""


class Repository(BaseModel):
    repository_id: str
    repository_name: str
    read_only: bool
    commit: str


def _parse_proposed_change_repositories(
    message: messages.RequestProposedChangePipeline, source: list[dict], destination: list[dict]
) -> list[ProposedChangeRepository]:
    """This function assumes that the repos is a list of the edges

    The data should come from the queries:
    * DESTINATION_ALLREPOSITORIES
    * SOURCE_REPOSITORIES
    * SOURCE_READONLY_REPOSITORIES
    """
    destination_repos = _parse_repositories(repositories=destination)
    source_repos = _parse_repositories(repositories=source)
    pc_repos: dict[str, ProposedChangeRepository] = {}
    for repo in destination_repos:
        if repo.repository_id not in pc_repos:
            pc_repos[repo.repository_id] = ProposedChangeRepository(
                repository_id=repo.repository_id,
                repository_name=repo.repository_name,
                read_only=repo.read_only,
                destination_commit=repo.commit,
                source_branch=message.source_branch,
                destination_branch=message.destination_branch,
            )
        else:
            pc_repos[repo.repository_id].destination_commit = repo.commit
    for repo in source_repos:
        if repo.repository_id not in pc_repos:
            pc_repos[repo.repository_id] = ProposedChangeRepository(
                repository_id=repo.repository_id,
                repository_name=repo.repository_name,
                read_only=repo.read_only,
                source_commit=repo.commit,
                source_branch=message.source_branch,
                destination_branch=message.destination_branch,
            )
        else:
            pc_repos[repo.repository_id].source_commit = repo.commit

    return list(pc_repos.values())


def _parse_repositories(repositories: list[dict]) -> list[Repository]:
    """This function assumes that the repos is a list of the edges

    The data should come from the queries:
    * DESTINATION_ALLREPOSITORIES
    * SOURCE_REPOSITORIES
    * SOURCE_READONLY_REPOSITORIES
    """
    parsed = []
    for repo in repositories:
        parsed.append(
            Repository(
                repository_id=repo["node"]["id"],
                repository_name=repo["node"]["name"]["value"],
                read_only=repo["node"]["__typename"] == "CoreReadOnlyRepository",
                commit=repo["node"]["commit"]["value"] or "",
            )
        )
    return parsed


async def _get_proposed_change_repositories(
    message: messages.RequestProposedChangePipeline, service: InfrahubServices
) -> list[ProposedChangeRepository]:
    destination_all = await service.client.execute_graphql(
        query=DESTINATION_ALLREPOSITORIES, branch_name=message.destination_branch
    )
    source_managed = await service.client.execute_graphql(
        query=SOURCE_REPOSITORIES, branch_name=message.source_branch, rebase=True
    )
    source_readonly = await service.client.execute_graphql(
        query=SOURCE_READONLY_REPOSITORIES, branch_name=message.source_branch, rebase=False
    )

    destination_all = destination_all["CoreGenericRepository"]["edges"]
    source_all = source_managed["CoreRepository"]["edges"] + source_readonly["CoreReadOnlyRepository"]["edges"]

    return _parse_proposed_change_repositories(message=message, source=source_all, destination=destination_all)


async def _validate_repository_merge_conflicts(repositories: List[ProposedChangeRepository]) -> bool:
    conflicts = False
    for repo in repositories:
        if repo.has_diff:
            git_repo = await InfrahubRepository.init(id=repo.repository_id, name=repo.repository_name)
            async with lock.registry.get(name=repo.repository_name, namespace="repository"):
                repo.conflicts = await git_repo.get_conflicts(
                    source_branch=repo.source_branch, dest_branch=repo.destination_branch
                )
                if repo.conflicts:
                    conflicts = True

    return conflicts


async def _gather_repository_repository_diffs(repositories: List[ProposedChangeRepository]) -> None:
    for repo in repositories:
        if repo.has_diff:
            git_repo = await InfrahubRepository.init(id=repo.repository_id, name=repo.repository_name)

            files_changed, files_added, files_removed = await git_repo.calculate_diff_between_commits(
                first_commit=repo.source_commit, second_commit=repo.destination_commit
            )
            repo.files_removed = files_removed
            repo.files_added = files_added
            repo.files_changed = files_changed
