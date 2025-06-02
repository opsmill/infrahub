from __future__ import annotations

from enum import IntFlag
from typing import TYPE_CHECKING

from prefect import flow, task
from prefect.logging import get_run_logger
from pydantic import BaseModel

from infrahub import lock
from infrahub.core.constants import CheckType, InfrahubKind, RepositoryInternalStatus
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.registry import registry
from infrahub.dependencies.registry import get_component_registry
from infrahub.git.models import TriggerRepositoryInternalChecks
from infrahub.git.repository import InfrahubRepository
from infrahub.message_bus import InfrahubMessage, messages
from infrahub.message_bus.types import (
    ProposedChangeArtifactDefinition,
    ProposedChangeBranchDiff,
    ProposedChangeRepository,
    ProposedChangeSubscriber,
)
from infrahub.proposed_change.branch_diff import (
    get_diff_summary_cache,
    get_modified_kinds,
    get_modified_node_ids,
    has_data_changes,
    has_node_changes,
    set_diff_summary_cache,
)
from infrahub.proposed_change.models import (
    RequestArtifactDefinitionCheck,
    RequestProposedChangeDataIntegrity,
    RequestProposedChangeRepositoryChecks,
    RequestProposedChangeRunGenerators,
    RequestProposedChangeSchemaIntegrity,
    RequestProposedChangeUserTests,
)
from infrahub.services import InfrahubServices  # noqa: TC001
from infrahub.workflows.catalogue import (
    GIT_REPOSITORY_INTERNAL_CHECKS_TRIGGER,
    REQUEST_ARTIFACT_DEFINITION_CHECK,
    REQUEST_PROPOSED_CHANGE_DATA_INTEGRITY,
    REQUEST_PROPOSED_CHANGE_REPOSITORY_CHECKS,
    REQUEST_PROPOSED_CHANGE_RUN_GENERATORS,
    REQUEST_PROPOSED_CHANGE_SCHEMA_INTEGRITY,
    REQUEST_PROPOSED_CHANGE_USER_TESTS,
)
from infrahub.workflows.utils import add_tags

if TYPE_CHECKING:
    from infrahub_sdk.diff import NodeDiff


class DefinitionSelect(IntFlag):
    NONE = 0
    MODIFIED_KINDS = 1
    FILE_CHANGES = 2

    @staticmethod
    def add_flag(current: DefinitionSelect, flag: DefinitionSelect, condition: bool) -> DefinitionSelect:
        if condition:
            return current | flag
        return current

    @property
    def log_line(self) -> str:
        change_types = []
        if DefinitionSelect.MODIFIED_KINDS in self:
            change_types.append("data changes within relevant object kinds")

        if DefinitionSelect.FILE_CHANGES in self:
            change_types.append("file modifications in Git repositories")

        if self:
            return f"Requesting generation due to {' and '.join(change_types)}"

        return "Doesn't require changes due to no relevant modified kinds or file changes in Git"


@flow(name="proposed-changed-pipeline", flow_run_name="Execute Pipeline")
async def pipeline(message: messages.RequestProposedChangePipeline, service: InfrahubServices) -> None:
    events: list[InfrahubMessage] = []

    repositories = await _get_proposed_change_repositories(message=message, service=service)

    if message.source_branch_sync_with_git and await _validate_repository_merge_conflicts(
        repositories=repositories, service=service
    ):
        for repo in repositories:
            if not repo.read_only and repo.internal_status == RepositoryInternalStatus.ACTIVE.value:
                model = TriggerRepositoryInternalChecks(
                    proposed_change=message.proposed_change,
                    repository=repo.repository_id,
                    source_branch=repo.source_branch,
                    target_branch=repo.destination_branch,
                )
                await service.workflow.submit_workflow(
                    workflow=GIT_REPOSITORY_INTERNAL_CHECKS_TRIGGER,
                    context=message.context,
                    parameters={"model": model},
                )
        return

    await _gather_repository_repository_diffs(repositories=repositories, service=service)

    async with service.database.start_session() as dbs:
        destination_branch = await registry.get_branch(db=dbs, branch=message.destination_branch)
        source_branch = await registry.get_branch(db=dbs, branch=message.source_branch)
        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=dbs, branch=source_branch)
        await diff_coordinator.update_branch_diff(base_branch=destination_branch, diff_branch=source_branch)

    diff_summary = await service.client.get_diff_summary(branch=message.source_branch)
    await set_diff_summary_cache(pipeline_id=message.pipeline_id, diff_summary=diff_summary, cache=service.cache)
    branch_diff = ProposedChangeBranchDiff(repositories=repositories, pipeline_id=message.pipeline_id)
    await _populate_subscribers(
        branch_diff=branch_diff, diff_summary=diff_summary, service=service, branch=message.source_branch
    )

    if message.check_type is CheckType.ARTIFACT:
        events.append(
            messages.RequestProposedChangeRefreshArtifacts(
                context=message.context,
                proposed_change=message.proposed_change,
                source_branch=message.source_branch,
                source_branch_sync_with_git=message.source_branch_sync_with_git,
                destination_branch=message.destination_branch,
                branch_diff=branch_diff,
            )
        )

    if message.check_type in [CheckType.ALL, CheckType.GENERATOR]:
        model_proposed_change_run_generator = RequestProposedChangeRunGenerators(
            proposed_change=message.proposed_change,
            source_branch=message.source_branch,
            source_branch_sync_with_git=message.source_branch_sync_with_git,
            destination_branch=message.destination_branch,
            branch_diff=branch_diff,
            refresh_artifacts=message.check_type is CheckType.ALL,
            do_repository_checks=message.check_type is CheckType.ALL,
        )
        await service.workflow.submit_workflow(
            workflow=REQUEST_PROPOSED_CHANGE_RUN_GENERATORS,
            context=message.context,
            parameters={"model": model_proposed_change_run_generator},
        )

    if message.check_type in [CheckType.ALL, CheckType.DATA] and has_node_changes(
        diff_summary=diff_summary, branch=message.source_branch
    ):
        model_proposed_change_data_integrity = RequestProposedChangeDataIntegrity(
            proposed_change=message.proposed_change,
            source_branch=message.source_branch,
            source_branch_sync_with_git=message.source_branch_sync_with_git,
            destination_branch=message.destination_branch,
            branch_diff=branch_diff,
        )
        await service.workflow.submit_workflow(
            workflow=REQUEST_PROPOSED_CHANGE_DATA_INTEGRITY,
            context=message.context,
            parameters={"model": model_proposed_change_data_integrity},
        )

    if message.check_type in [CheckType.REPOSITORY, CheckType.USER]:
        model_proposed_change_repo_checks = RequestProposedChangeRepositoryChecks(
            proposed_change=message.proposed_change,
            source_branch=message.source_branch,
            source_branch_sync_with_git=message.source_branch_sync_with_git,
            destination_branch=message.destination_branch,
            branch_diff=branch_diff,
        )
        await service.workflow.submit_workflow(
            workflow=REQUEST_PROPOSED_CHANGE_REPOSITORY_CHECKS,
            context=message.context,
            parameters={"model": model_proposed_change_repo_checks},
        )

    if message.check_type in [CheckType.ALL, CheckType.SCHEMA] and has_data_changes(
        diff_summary=diff_summary, branch=message.source_branch
    ):
        await service.workflow.submit_workflow(
            workflow=REQUEST_PROPOSED_CHANGE_SCHEMA_INTEGRITY,
            context=message.context,
            parameters={
                "model": RequestProposedChangeSchemaIntegrity(
                    proposed_change=message.proposed_change,
                    source_branch=message.source_branch,
                    source_branch_sync_with_git=message.source_branch_sync_with_git,
                    destination_branch=message.destination_branch,
                    branch_diff=branch_diff,
                )
            },
        )

    if message.check_type in [CheckType.ALL, CheckType.TEST]:
        await service.workflow.submit_workflow(
            workflow=REQUEST_PROPOSED_CHANGE_USER_TESTS,
            context=message.context,
            parameters={
                "model": RequestProposedChangeUserTests(
                    proposed_change=message.proposed_change,
                    source_branch=message.source_branch,
                    source_branch_sync_with_git=message.source_branch_sync_with_git,
                    destination_branch=message.destination_branch,
                    branch_diff=branch_diff,
                )
            },
        )

    for event in events:
        event.assign_meta(parent=message)
        await service.message_bus.send(message=event)


@flow(
    name="proposed-changed-refresh-artifact",
    flow_run_name="Trigger artifacts refresh",
)
async def refresh_artifacts(message: messages.RequestProposedChangeRefreshArtifacts, service: InfrahubServices) -> None:
    await add_tags(branches=[message.source_branch], nodes=[message.proposed_change])
    log = get_run_logger()

    definition_information = await service.client.execute_graphql(
        query=GATHER_ARTIFACT_DEFINITIONS,
        branch_name=message.source_branch,
    )
    artifact_definitions = _parse_artifact_definitions(
        definitions=definition_information[InfrahubKind.ARTIFACTDEFINITION]["edges"]
    )

    diff_summary = await get_diff_summary_cache(pipeline_id=message.branch_diff.pipeline_id, cache=service.cache)
    modified_kinds = get_modified_kinds(diff_summary=diff_summary, branch=message.source_branch)

    for artifact_definition in artifact_definitions:
        # Request artifact definition checks if the source branch that is managed in combination
        # to the Git repository containing modifications which could indicate changes to the transforms
        # in code
        # Alternatively if the queries used touches models that have been modified in the path
        # impacted artifact definitions will be included for consideration

        select = DefinitionSelect.NONE
        select = select.add_flag(
            current=select,
            flag=DefinitionSelect.FILE_CHANGES,
            condition=message.source_branch_sync_with_git and message.branch_diff.has_file_modifications,
        )

        for changed_model in modified_kinds:
            condition = False
            if (changed_model in artifact_definition.query_models) or (
                changed_model.startswith("Profile")
                and changed_model.replace("Profile", "", 1) in artifact_definition.query_models
            ):
                condition = True

            select = select.add_flag(
                current=select,
                flag=DefinitionSelect.MODIFIED_KINDS,
                condition=condition,
            )

        if select:
            log.info(f"Trigger processing of {artifact_definition.definition_name}")
            model = RequestArtifactDefinitionCheck(
                context=message.context,
                artifact_definition=artifact_definition,
                branch_diff=message.branch_diff,
                proposed_change=message.proposed_change,
                source_branch=message.source_branch,
                source_branch_sync_with_git=message.source_branch_sync_with_git,
                destination_branch=message.destination_branch,
            )

            await service.workflow.submit_workflow(REQUEST_ARTIFACT_DEFINITION_CHECK, parameters={"model": model})


GATHER_ARTIFACT_DEFINITIONS = """
query GatherArtifactDefinitions {
  CoreArtifactDefinition {
    edges {
      node {
        id
        name {
          value
        }
        artifact_name {
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
              convert_query_response {
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
        internal_status {
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
        internal_status {
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
        internal_status {
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
    internal_status: str


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
                internal_status=repo.internal_status,
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
                internal_status=repo.internal_status,
                source_commit=repo.commit,
                source_branch=message.source_branch,
                destination_branch=message.destination_branch,
            )
        else:
            pc_repos[repo.repository_id].source_commit = repo.commit
            pc_repos[repo.repository_id].internal_status = repo.internal_status

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
                read_only=repo["node"]["__typename"] == InfrahubKind.READONLYREPOSITORY,
                commit=repo["node"]["commit"]["value"] or "",
                internal_status=repo["node"]["internal_status"]["value"],
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
            artifact_name=definition["node"]["artifact_name"]["value"],
            content_type=definition["node"]["content_type"]["value"],
            timeout=definition["node"]["transformation"]["node"]["timeout"]["value"],
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
            artifact_definition.convert_query_response = definition["node"]["transformation"]["node"][
                "convert_query_response"
            ]["value"]

        parsed.append(artifact_definition)

    return parsed


async def _get_proposed_change_repositories(
    message: messages.RequestProposedChangePipeline, service: InfrahubServices
) -> list[ProposedChangeRepository]:
    destination_all = await service.client.execute_graphql(
        query=DESTINATION_ALLREPOSITORIES, branch_name=message.destination_branch
    )
    source_managed = await service.client.execute_graphql(query=SOURCE_REPOSITORIES, branch_name=message.source_branch)
    source_readonly = await service.client.execute_graphql(
        query=SOURCE_READONLY_REPOSITORIES, branch_name=message.source_branch
    )

    destination_all = destination_all[InfrahubKind.GENERICREPOSITORY]["edges"]
    source_all = (
        source_managed[InfrahubKind.REPOSITORY]["edges"] + source_readonly[InfrahubKind.READONLYREPOSITORY]["edges"]
    )

    return _parse_proposed_change_repositories(message=message, source=source_all, destination=destination_all)


@task(name="proposed-change-validate-repository-conflicts", task_run_name="Validate conflicts on repository")  # type: ignore[arg-type]
async def _validate_repository_merge_conflicts(
    repositories: list[ProposedChangeRepository], service: InfrahubServices
) -> bool:
    log = get_run_logger()
    conflicts = False
    for repo in repositories:
        if repo.has_diff and not repo.is_staging:
            git_repo = await InfrahubRepository.init(
                id=repo.repository_id,
                name=repo.repository_name,
                client=service.client,
                service=service,
            )
            async with lock.registry.get(name=repo.repository_name, namespace="repository"):
                repo.conflicts = await git_repo.get_conflicts(
                    source_branch=repo.source_branch, dest_branch=repo.destination_branch
                )
                if repo.conflicts:
                    log.info(f"{len(repo.conflicts)} conflict(s) identified on {repo.repository_name}")
                    conflicts = True
                else:
                    log.info(f"no conflict identified for {repo.repository_name}")

    return conflicts


async def _gather_repository_repository_diffs(
    repositories: list[ProposedChangeRepository], service: InfrahubServices
) -> None:
    for repo in repositories:
        if repo.has_diff and repo.source_commit and repo.destination_commit:
            # TODO we need to find a way to return all files in the repo if the repo is new
            git_repo = await InfrahubRepository.init(
                id=repo.repository_id,
                name=repo.repository_name,
                client=service.client,
                service=service,
            )

            files_changed: list[str] = []
            files_added: list[str] = []
            files_removed: list[str] = []

            if repo.destination_branch:
                files_changed, files_added, files_removed = await git_repo.calculate_diff_between_commits(
                    first_commit=repo.source_commit, second_commit=repo.destination_commit
                )
            else:
                files_added = await git_repo.list_all_files(commit=repo.source_commit)

            repo.files_removed = files_removed
            repo.files_added = files_added
            repo.files_changed = files_changed


async def _populate_subscribers(
    branch_diff: ProposedChangeBranchDiff, diff_summary: list[NodeDiff], service: InfrahubServices, branch: str
) -> None:
    result = await service.client.execute_graphql(
        query=GATHER_GRAPHQL_QUERY_SUBSCRIBERS,
        branch_name=branch,
        variables={"members": get_modified_node_ids(diff_summary=diff_summary, branch=branch)},
    )

    for group in result[InfrahubKind.GRAPHQLQUERYGROUP]["edges"]:
        for subscriber in group["node"]["subscribers"]["edges"]:
            branch_diff.subscribers.append(
                ProposedChangeSubscriber(subscriber_id=subscriber["node"]["id"], kind=subscriber["node"]["__typename"])
            )
