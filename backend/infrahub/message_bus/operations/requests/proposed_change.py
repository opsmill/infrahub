from __future__ import annotations

import asyncio
from enum import IntFlag
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Union

import pytest
from pydantic import BaseModel

from infrahub import config, lock
from infrahub.core.constants import (
    CheckType,
    InfrahubKind,
    ProposedChangeState,
)
from infrahub.core.diff import BranchDiffer, SchemaConflict
from infrahub.core.integrity.object_conflict.conflict_recorder import ObjectConflictValidatorRecorder
from infrahub.core.registry import registry
from infrahub.core.validators.checker import schema_validators_checker
from infrahub.git.repository import InfrahubRepository, get_initialized_repo
from infrahub.log import get_logger
from infrahub.message_bus import InfrahubMessage, messages
from infrahub.message_bus.types import (
    ProposedChangeArtifactDefinition,
    ProposedChangeBranchDiff,
    ProposedChangeRepository,
    ProposedChangeSubscriber,
)
from infrahub.pytest_plugin import InfrahubBackendPlugin

if TYPE_CHECKING:
    from infrahub_sdk.node import InfrahubNode

    from infrahub.core.schema_manager import SchemaBranch, SchemaUpdateConstraintInfo
    from infrahub.services import InfrahubServices


log = get_logger()


class ArtifactSelect(IntFlag):
    NONE = 0
    MODIFIED_KINDS = 1
    FILE_CHANGES = 2

    @staticmethod
    def add_flag(current: ArtifactSelect, flag: ArtifactSelect, condition: bool):
        if condition:
            return current | flag
        return current

    @property
    def log_line(self) -> str:
        change_types = []
        if ArtifactSelect.MODIFIED_KINDS in self:
            change_types.append("data changes within relevant object kinds")

        if ArtifactSelect.FILE_CHANGES in self:
            change_types.append("file modifications in Git repositories")

        if self:
            return f"Requesting Artifact Definition generation due to {' and '.join(change_types)}"

        return "Artifact Definition doesn't require changes due to no relevant modified kinds or file changes in Git"


async def cancel(message: messages.RequestProposedChangeCancel, service: InfrahubServices) -> None:
    """Cancel a proposed change."""
    async with service.task_report(
        related_node=message.proposed_change,
        title="Canceling proposed change",
    ) as task_report:
        await task_report.log.info(
            "Canceling proposed change as the source branch was deleted", id=message.proposed_change
        )
        proposed_change = await service.client.get(kind=InfrahubKind.PROPOSEDCHANGE, id=message.proposed_change)
        proposed_change.state.value = ProposedChangeState.CANCELED.value
        await proposed_change.save()


async def data_integrity(message: messages.RequestProposedChangeDataIntegrity, service: InfrahubServices) -> None:
    """Triggers a data integrity validation check on the provided proposed change to start."""
    async with service.task_report(
        related_node=message.proposed_change,
        title="Data Integrity",
    ):
        log.info(f"Got a request to process data integrity defined in proposed_change: {message.proposed_change}")

        source_branch = await registry.get_branch(db=service.database, branch=message.source_branch)
        diff = await BranchDiffer.init(db=service.database, branch=source_branch, branch_only=False)
        conflicts = await diff.get_conflicts_graph()

        async with service.database.start_transaction() as db:
            object_conflict_validator_recorder = ObjectConflictValidatorRecorder(
                db=db,
                validator_kind=InfrahubKind.DATAVALIDATOR,
                validator_label="Data Integrity",
                check_schema_kind=InfrahubKind.DATACHECK,
            )
            await object_conflict_validator_recorder.record_conflicts(message.proposed_change, conflicts)


async def pipeline(message: messages.RequestProposedChangePipeline, service: InfrahubServices) -> None:
    async with service.task_report(
        related_node=message.proposed_change,
        title="Starting pipeline",
    ) as task_report:
        await task_report.info("Initiating pipeline", proposed_change=message.proposed_change)
        events: list[InfrahubMessage] = []

        repositories = await _get_proposed_change_repositories(message=message, service=service)
        await task_report.info(
            f"Identified {len(repositories)} repositories connected to the proposed change",
            proposed_change=message.proposed_change,
        )

        if not message.source_branch_data_only and await _validate_repository_merge_conflicts(
            repositories=repositories
        ):
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
            await task_report.error("Pipeline aborted due to merge conflicts", proposed_change=message.proposed_change)
            return

        await _gather_repository_repository_diffs(repositories=repositories)

        diff_summary = await service.client.get_diff_summary(branch=message.source_branch)
        branch_diff = ProposedChangeBranchDiff(diff_summary=diff_summary, repositories=repositories)
        await _populate_subscribers(branch_diff=branch_diff, service=service, branch=message.source_branch)

        if message.check_type in [CheckType.ALL, CheckType.ARTIFACT]:
            await task_report.info("Adding Refresh Artifact job", proposed_change=message.proposed_change)
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
            await task_report.info("Adding Data Integrity job", proposed_change=message.proposed_change)
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
            await task_report.info("Adding Repository Check job", proposed_change=message.proposed_change)
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
            await task_report.info("Adding Schema Integrity job", proposed_change=message.proposed_change)
            events.append(
                messages.RequestProposedChangeSchemaIntegrity(
                    proposed_change=message.proposed_change,
                    source_branch=message.source_branch,
                    source_branch_data_only=message.source_branch_data_only,
                    destination_branch=message.destination_branch,
                    branch_diff=branch_diff,
                )
            )

        if message.check_type in [CheckType.ALL, CheckType.TEST]:
            await task_report.info("Adding Repository Test job", proposed_change=message.proposed_change)
            events.append(
                messages.RequestProposedChangeRunTests(
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
    async with service.task_report(
        related_node=message.proposed_change,
        title="Schema Integrity",
    ):
        log.info(f"Got a request to process schema integrity defined in proposed_change: {message.proposed_change}")

        # For now, we retrieve the latest schema for each branch from the registry
        # In the future it would be good to generate the object SchemaUpdateValidationResult from message.branch_diff
        source_schema = registry.schema.get_schema_branch(name=message.source_branch).duplicate()
        dest_schema = registry.schema.get_schema_branch(name=message.destination_branch).duplicate()

        candidate_schema = dest_schema.duplicate()
        candidate_schema.update(schema=source_schema)
        validation_result = dest_schema.validate_update(other=candidate_schema)

        constraints_from_data_diff = await _get_proposed_change_schema_integrity_constraints(
            message=message, dest_schema=candidate_schema
        )
        constraints_from_schema_diff = validation_result.constraints
        constraints = set(constraints_from_data_diff + constraints_from_schema_diff)

        if not constraints:
            return

        # ----------------------------------------------------------
        # Validate if the new schema is valid with the content of the database
        # ----------------------------------------------------------
        source_branch = registry.get_branch_from_registry(branch=message.source_branch)
        source_branch.ephemeral_rebase = True
        _, responses = await schema_validators_checker(
            branch=source_branch, schema=candidate_schema, constraints=constraints, service=service
        )

        # TODO we need to report a failure if an error happened during the execution of a validator
        conflicts: List[SchemaConflict] = []
        for response in responses:
            for violation in response.data.violations:
                conflicts.append(
                    SchemaConflict(
                        name=response.data.schema_path.get_path(),
                        type=response.data.constraint_name,
                        kind=violation.node_kind,
                        id=violation.node_id,
                        path=response.data.schema_path.get_path(),
                        value="NA",
                        branch="placeholder",
                    )
                )

        if not conflicts:
            return

        async with service.database.start_transaction() as db:
            object_conflict_validator_recorder = ObjectConflictValidatorRecorder(
                db=db,
                validator_kind=InfrahubKind.SCHEMAVALIDATOR,
                validator_label="Schema Integrity",
                check_schema_kind=InfrahubKind.SCHEMACHECK,
            )
            await object_conflict_validator_recorder.record_conflicts(
                proposed_change_id=message.proposed_change, conflicts=conflicts
            )


async def repository_checks(message: messages.RequestProposedChangeRepositoryChecks, service: InfrahubServices) -> None:
    async with service.task_report(
        related_node=message.proposed_change,
        title="Evaluating Repository Checks",
    ):
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
    async with service.task_report(
        related_node=message.proposed_change,
        title="Evaluating Artifact Checks",
    ) as task_report:
        log.info(f"Refreshing artifacts for change_proposal={message.proposed_change}")
        definition_information = await service.client.execute_graphql(
            query=GATHER_ARTIFACT_DEFINITIONS,
            branch_name=message.source_branch,
        )
        artifact_definitions = _parse_artifact_definitions(
            definitions=definition_information["CoreArtifactDefinition"]["edges"]
        )

        await task_report.info(
            f"Available artifact definitions: {', '.join(sorted([artdef.definition_name for artdef in artifact_definitions]))}",
            proposed_change=message.proposed_change,
        )

        for artifact_definition in artifact_definitions:
            # Request artifact definition checks if the source branch that is managed in combination
            # to the Git repository containing modifications which could indicate changes to the transforms
            # in code
            # Alternatively if the queries used touches models that have been modified in the path
            # impacted artifact definitions will be included for consideration

            select = ArtifactSelect.NONE
            select = select.add_flag(
                current=select,
                flag=ArtifactSelect.FILE_CHANGES,
                condition=not message.source_branch_data_only and message.branch_diff.has_file_modifications,
            )

            for changed_model in message.branch_diff.modified_kinds(branch=message.source_branch):
                select = select.add_flag(
                    current=select,
                    flag=ArtifactSelect.MODIFIED_KINDS,
                    condition=changed_model in artifact_definition.query_models,
                )

            await task_report.info(f"{select.log_line}: {artifact_definition.definition_name}")

            if select:
                msg = messages.RequestArtifactDefinitionCheck(
                    artifact_definition=artifact_definition,
                    branch_diff=message.branch_diff,
                    proposed_change=message.proposed_change,
                    source_branch=message.source_branch,
                    source_branch_data_only=message.source_branch_data_only,
                    destination_branch=message.destination_branch,
                )

                msg.assign_meta(parent=message)
                await service.send(message=msg)


GATHER_ARTIFACT_DEFINITIONS = """
query GatherArtifactDefinitions {
  CoreArtifactDefinition {
    edges {
      node {
        id
        name {
          value
        }
        content_type {
            value
        }
        transformation {
          node {
            __typename
            timeout {
                value
            }
            rebase {
                value
            }
            query {
              node {
                models {
                  value
                }
                name {
                  value
                }
              }
            }
            ... on CoreTransformJinja2 {
              template_path {
                value
              }
            }
            ... on CoreTransformPython {
              class_name {
                value
              }
              file_path {
                value
              }
            }
            repository {
              node {
                id
              }
            }
          }
        }
      }
    }
  }
}
"""

GATHER_GRAPHQL_QUERY_SUBSCRIBERS = """
query GatherGraphQLQuerySubscribers($members: [ID!]) {
  CoreGraphQLQueryGroup(members__ids: $members) {
    edges {
      node {
        subscribers {
          edges {
            node {
              id
              __typename
            }
          }
        }
      }
    }
  }
}
"""


async def run_tests(message: messages.RequestProposedChangeRunTests, service: InfrahubServices) -> None:
    async with service.task_report(
        related_node=message.proposed_change,
        title="Running repository tests",
    ):
        log.info("running_repository_tests", proposed_change=message.proposed_change)
        proposed_change = await service.client.get(kind=InfrahubKind.PROPOSEDCHANGE, id=message.proposed_change)

        def _execute(
            directory: Path, repository: ProposedChangeRepository, proposed_change: InfrahubNode
        ) -> Union[int, pytest.ExitCode]:
            config_file = str(directory / ".infrahub.yml")
            return pytest.main(
                [
                    str(directory),
                    f"--infrahub-repo-config={config_file}",
                    f"--infrahub-address={config.SETTINGS.main.internal_address}",
                    "--continue-on-collection-errors",  # FIXME: Non-Infrahub tests should be ignored
                    "-qqqq",
                    "-s",
                ],
                plugins=[InfrahubBackendPlugin(service.client.config, repository.repository_id, proposed_change.id)],
            )

        for repository in message.branch_diff.repositories:
            if not message.source_branch_data_only:
                repo = await get_initialized_repo(
                    repository_id=repository.repository_id,
                    name=repository.repository_name,
                    service=service,
                    repository_kind=repository.kind,
                )
                commit = repo.get_commit_value(proposed_change.source_branch.value)
                worktree_directory = Path(repo.get_commit_worktree(commit=commit).directory)

                return_code = await asyncio.to_thread(_execute, worktree_directory, repository, proposed_change)
                log.info(
                    "repository_tests_completed",
                    proposed_change=message.proposed_change,
                    repository=repository.repository_name,
                    return_code=return_code,
                )


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


def _parse_artifact_definitions(definitions: list[dict]) -> list[ProposedChangeArtifactDefinition]:
    """This function assumes that definitions is a list of the edges

    The edge should be of type CoreArtifactDefinition from the query
    * GATHER_ARTIFACT_DEFINITIONS
    """

    parsed = []
    for definition in definitions:
        artifact_definition = ProposedChangeArtifactDefinition(
            definition_id=definition["node"]["id"],
            definition_name=definition["node"]["name"]["value"],
            content_type=definition["node"]["content_type"]["value"],
            timeout=definition["node"]["transformation"]["node"]["timeout"]["value"],
            rebase=definition["node"]["transformation"]["node"]["rebase"]["value"],
            query_name=definition["node"]["transformation"]["node"]["query"]["node"]["name"]["value"],
            query_models=definition["node"]["transformation"]["node"]["query"]["node"]["models"]["value"] or [],
            repository_id=definition["node"]["transformation"]["node"]["repository"]["node"]["id"],
            transform_kind=definition["node"]["transformation"]["node"]["__typename"],
        )
        if artifact_definition.transform_kind == InfrahubKind.TRANSFORMJINJA2:
            artifact_definition.template_path = definition["node"]["transformation"]["node"]["template_path"]["value"]
        elif artifact_definition.transform_kind == InfrahubKind.TRANSFORMPYTHON:
            artifact_definition.class_name = definition["node"]["transformation"]["node"]["class_name"]["value"]
            artifact_definition.file_path = definition["node"]["transformation"]["node"]["file_path"]["value"]

        parsed.append(artifact_definition)

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


async def _populate_subscribers(branch_diff: ProposedChangeBranchDiff, service: InfrahubServices, branch: str) -> None:
    result = await service.client.execute_graphql(
        query=GATHER_GRAPHQL_QUERY_SUBSCRIBERS,
        branch_name=branch,
        variables={"members": branch_diff.modified_nodes(branch=branch)},
    )

    for group in result["CoreGraphQLQueryGroup"]["edges"]:
        for subscriber in group["node"]["subscribers"]["edges"]:
            branch_diff.subscribers.append(
                ProposedChangeSubscriber(subscriber_id=subscriber["node"]["id"], kind=subscriber["node"]["__typename"])
            )


async def _get_proposed_change_schema_integrity_constraints(
    message: messages.RequestProposedChangeSchemaIntegrity,
    dest_schema: SchemaBranch,
    source_schema: Optional[SchemaBranch] = None,
) -> List[SchemaUpdateConstraintInfo]:
    # For now we run the constraints for all models that have changed in the source branch or the destination branch
    # We need to revisit that to properly calculate which constraints we should validate
    modified_kinds = {node_diff["kind"] for node_diff in message.branch_diff.diff_summary}

    constraints: List[SchemaUpdateConstraintInfo] = []
    for kind in modified_kinds:
        constraints.extend(await dest_schema.get_constraints_per_model(name=kind, source_schema_branch=source_schema))

    return constraints
