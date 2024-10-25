from __future__ import annotations

import asyncio
import os
import sys
from enum import IntFlag
from pathlib import Path
from typing import TYPE_CHECKING, Union

import pytest
from infrahub_sdk.protocols import CoreGeneratorDefinition, CoreProposedChange
from prefect import flow
from pydantic import BaseModel

from infrahub import config, lock
from infrahub.core.constants import CheckType, InfrahubKind, ProposedChangeState, RepositoryInternalStatus
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.model.diff import DiffElementType, SchemaConflict
from infrahub.core.diff.model.path import NodeDiffFieldSummary
from infrahub.core.integrity.object_conflict.conflict_recorder import ObjectConflictValidatorRecorder
from infrahub.core.registry import registry
from infrahub.core.validators.checker import schema_validators_checker
from infrahub.core.validators.determiner import ConstraintValidatorDeterminer
from infrahub.dependencies.registry import get_component_registry
from infrahub.git.repository import InfrahubRepository, get_initialized_repo
from infrahub.log import get_logger
from infrahub.message_bus import InfrahubMessage, messages
from infrahub.message_bus.types import (
    ProposedChangeArtifactDefinition,
    ProposedChangeBranchDiff,
    ProposedChangeGeneratorDefinition,
    ProposedChangeRepository,
    ProposedChangeSubscriber,
)
from infrahub.pytest_plugin import InfrahubBackendPlugin
from infrahub.services import InfrahubServices  # noqa: TCH001

if TYPE_CHECKING:
    from infrahub_sdk.node import InfrahubNode

    from infrahub.core.models import SchemaUpdateConstraintInfo
    from infrahub.core.schema.schema_branch import SchemaBranch


log = get_logger()


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


@flow(name="proposed-changed-cancel")
async def cancel(message: messages.RequestProposedChangeCancel, service: InfrahubServices) -> None:
    """Cancel a proposed change."""
    async with service.task_report(
        related_node=message.proposed_change,
        title="Canceling proposed change",
    ) as task_report:
        await task_report.info("Canceling proposed change as the source branch was deleted", id=message.proposed_change)
        proposed_change = await service.client.get(kind=CoreProposedChange, id=message.proposed_change)
        proposed_change.state.value = ProposedChangeState.CANCELED.value
        await proposed_change.save()


@flow(name="proposed-changed-data-integrity")
async def data_integrity(message: messages.RequestProposedChangeDataIntegrity, service: InfrahubServices) -> None:
    """Triggers a data integrity validation check on the provided proposed change to start."""
    async with service.task_report(
        related_node=message.proposed_change,
        title="Data Integrity",
    ):
        log.info(f"Got a request to process data integrity defined in proposed_change: {message.proposed_change}")

        destination_branch = await registry.get_branch(db=service.database, branch=message.destination_branch)
        source_branch = await registry.get_branch(db=service.database, branch=message.source_branch)
        component_registry = get_component_registry()
        async with service.database.start_transaction() as dbt:
            diff_coordinator = await component_registry.get_component(DiffCoordinator, db=dbt, branch=source_branch)
            await diff_coordinator.update_branch_diff(base_branch=destination_branch, diff_branch=source_branch)


@flow(name="proposed-changed-pipeline")
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

        if message.source_branch_sync_with_git and await _validate_repository_merge_conflicts(
            repositories=repositories
        ):
            for repo in repositories:
                if not repo.read_only and repo.internal_status == RepositoryInternalStatus.ACTIVE.value:
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

        destination_branch = await registry.get_branch(db=service.database, branch=message.destination_branch)
        source_branch = await registry.get_branch(db=service.database, branch=message.source_branch)
        component_registry = get_component_registry()
        async with service.database.start_transaction() as dbt:
            diff_coordinator = await component_registry.get_component(DiffCoordinator, db=dbt, branch=source_branch)
            await diff_coordinator.update_branch_diff(base_branch=destination_branch, diff_branch=source_branch)
        diff_summary = await service.client.get_diff_summary(branch=message.source_branch)
        branch_diff = ProposedChangeBranchDiff(diff_summary=diff_summary, repositories=repositories)
        await _populate_subscribers(branch_diff=branch_diff, service=service, branch=message.source_branch)

        if message.check_type is CheckType.ARTIFACT:
            await task_report.info("Adding Refresh Artifact job", proposed_change=message.proposed_change)
            events.append(
                messages.RequestProposedChangeRefreshArtifacts(
                    proposed_change=message.proposed_change,
                    source_branch=message.source_branch,
                    source_branch_sync_with_git=message.source_branch_sync_with_git,
                    destination_branch=message.destination_branch,
                    branch_diff=branch_diff,
                )
            )

        if message.check_type in [CheckType.ALL, CheckType.GENERATOR]:
            await task_report.info("Adding Run Generators job", proposed_change=message.proposed_change)
            events.append(
                messages.RequestProposedChangeRunGenerators(
                    proposed_change=message.proposed_change,
                    source_branch=message.source_branch,
                    source_branch_sync_with_git=message.source_branch_sync_with_git,
                    destination_branch=message.destination_branch,
                    branch_diff=branch_diff,
                    refresh_artifacts=message.check_type is CheckType.ALL,
                    do_repository_checks=message.check_type is CheckType.ALL,
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
                    source_branch_sync_with_git=message.source_branch_sync_with_git,
                    destination_branch=message.destination_branch,
                    branch_diff=branch_diff,
                )
            )

        if message.check_type in [CheckType.REPOSITORY, CheckType.USER]:
            await task_report.info("Adding Repository Check job", proposed_change=message.proposed_change)
            events.append(
                messages.RequestProposedChangeRepositoryChecks(
                    proposed_change=message.proposed_change,
                    source_branch=message.source_branch,
                    source_branch_sync_with_git=message.source_branch_sync_with_git,
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
                    source_branch_sync_with_git=message.source_branch_sync_with_git,
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
                    source_branch_sync_with_git=message.source_branch_sync_with_git,
                    destination_branch=message.destination_branch,
                    branch_diff=branch_diff,
                )
            )

        for event in events:
            event.assign_meta(parent=message)
            await service.send(message=event)


@flow(name="proposed-changed-schema-integrity")
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
            message=message, schema=candidate_schema
        )
        constraints_from_schema_diff = validation_result.constraints
        constraints = set(constraints_from_data_diff + constraints_from_schema_diff)

        if not constraints:
            return

        # ----------------------------------------------------------
        # Validate if the new schema is valid with the content of the database
        # ----------------------------------------------------------
        source_branch = registry.get_branch_from_registry(branch=message.source_branch)
        _, responses = await schema_validators_checker(
            branch=source_branch, schema=candidate_schema, constraints=list(constraints), service=service
        )

        # TODO we need to report a failure if an error happened during the execution of a validator
        conflicts: list[SchemaConflict] = []
        for response in responses:
            for violation in response.data.violations:
                conflicts.append(
                    SchemaConflict(
                        name=response.data.schema_path.get_path(),
                        type=response.data.constraint_name,
                        kind=violation.node_kind,
                        id=violation.node_id,
                        path=response.data.schema_path.get_path(),
                        value=violation.message,
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


@flow(name="proposed-changed-repository-check")
async def repository_checks(message: messages.RequestProposedChangeRepositoryChecks, service: InfrahubServices) -> None:
    async with service.task_report(
        related_node=message.proposed_change,
        title=f"Evaluating Repository Checks {len(message.branch_diff.repositories)} repositories",
    ) as task_report:
        log.info(f"Got a request to process checks defined in proposed_change: {message.proposed_change}")
        events: list[InfrahubMessage] = []
        for repository in message.branch_diff.repositories:
            log_line = "Skipping merge conflict checks for data only branch"
            if (
                message.source_branch_sync_with_git
                and not repository.read_only
                and repository.internal_status == RepositoryInternalStatus.ACTIVE.value
            ):
                events.append(
                    messages.RequestRepositoryChecks(
                        proposed_change=message.proposed_change,
                        repository=repository.repository_id,
                        source_branch=message.source_branch,
                        target_branch=message.destination_branch,
                    )
                )
                log_line = "Requesting merge conflict checks"
            await task_report.info(f"{repository.repository_name}: {log_line}")
            events.append(
                messages.RequestRepositoryUserChecks(
                    proposed_change=message.proposed_change,
                    repository=repository.repository_id,
                    source_branch=message.source_branch,
                    source_branch_sync_with_git=message.source_branch_sync_with_git,
                    target_branch=message.destination_branch,
                    branch_diff=message.branch_diff,
                )
            )
            await task_report.info(f"{repository.repository_name}: Requesting user checks")
        for event in events:
            event.assign_meta(parent=message)
            await service.send(message=event)


@flow(name="proposed-changed-refresh-artifact")
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
            definitions=definition_information[InfrahubKind.ARTIFACTDEFINITION]["edges"]
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

            select = DefinitionSelect.NONE
            select = select.add_flag(
                current=select,
                flag=DefinitionSelect.FILE_CHANGES,
                condition=message.source_branch_sync_with_git and message.branch_diff.has_file_modifications,
            )

            for changed_model in message.branch_diff.modified_kinds(branch=message.source_branch):
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

            await task_report.info(f"{artifact_definition.definition_name}: {select.log_line}")

            if select:
                msg = messages.RequestArtifactDefinitionCheck(
                    artifact_definition=artifact_definition,
                    branch_diff=message.branch_diff,
                    proposed_change=message.proposed_change,
                    source_branch=message.source_branch,
                    source_branch_sync_with_git=message.source_branch_sync_with_git,
                    destination_branch=message.destination_branch,
                )

                msg.assign_meta(parent=message)
                await service.send(message=msg)


@flow(name="proposed-changed-run-generator")
async def run_generators(message: messages.RequestProposedChangeRunGenerators, service: InfrahubServices) -> None:
    async with service.task_report(
        related_node=message.proposed_change,
        title="Evaluating Generators",
    ) as task_report:
        generators: list[CoreGeneratorDefinition] = await service.client.filters(
            kind=InfrahubKind.GENERATORDEFINITION,
            prefetch_relationships=True,
            populate_store=True,
            branch=message.source_branch,
        )
        generator_definitions = [
            ProposedChangeGeneratorDefinition(
                definition_id=generator.id,
                definition_name=generator.name.value,
                class_name=generator.class_name.value,
                file_path=generator.file_path.value,
                query_name=generator.query.peer.name.value,
                query_models=generator.query.peer.models.value,
                repository_id=generator.repository.peer.id,
                parameters=generator.parameters.value,
                group_id=generator.targets.peer.id,
                convert_query_response=generator.convert_query_response.value,
            )
            for generator in generators
        ]

        for generator_definition in generator_definitions:
            # Request generator definitions if the source branch that is managed in combination
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

            for changed_model in message.branch_diff.modified_kinds(branch=message.source_branch):
                select = select.add_flag(
                    current=select,
                    flag=DefinitionSelect.MODIFIED_KINDS,
                    condition=changed_model in generator_definition.query_models,
                )

            await task_report.info(f"{generator_definition.definition_name}: {select.log_line}")

            if select:
                msg = messages.RequestGeneratorDefinitionCheck(
                    generator_definition=generator_definition,
                    branch_diff=message.branch_diff,
                    proposed_change=message.proposed_change,
                    source_branch=message.source_branch,
                    source_branch_sync_with_git=message.source_branch_sync_with_git,
                    destination_branch=message.destination_branch,
                )
                msg.assign_meta(parent=message)
                await service.send(message=msg)

    next_messages: list[InfrahubMessage] = []
    if message.refresh_artifacts:
        await task_report.info("Adding Refresh Artifact job", proposed_change=message.proposed_change)
        next_messages.append(
            messages.RequestProposedChangeRefreshArtifacts(
                proposed_change=message.proposed_change,
                source_branch=message.source_branch,
                source_branch_sync_with_git=message.source_branch_sync_with_git,
                destination_branch=message.destination_branch,
                branch_diff=message.branch_diff,
            )
        )

    if message.do_repository_checks:
        await task_report.info("Adding Repository Check job", proposed_change=message.proposed_change)
        next_messages.append(
            messages.RequestProposedChangeRepositoryChecks(
                proposed_change=message.proposed_change,
                source_branch=message.source_branch,
                source_branch_sync_with_git=message.source_branch_sync_with_git,
                destination_branch=message.destination_branch,
                branch_diff=message.branch_diff,
            )
        )

    for next_msg in next_messages:
        next_msg.assign_meta(parent=message)
        await service.send(message=next_msg)


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


@flow(name="proposed-changed-run-tests")
async def run_tests(message: messages.RequestProposedChangeRunTests, service: InfrahubServices) -> None:
    async with service.task_report(
        related_node=message.proposed_change,
        title=f"Running repository tests ({len(message.branch_diff.repositories)} repositories)",
    ) as task_report:
        log.info("running_repository_tests", proposed_change=message.proposed_change)
        proposed_change = await service.client.get(kind=InfrahubKind.PROPOSEDCHANGE, id=message.proposed_change)

        def _execute(
            directory: Path, repository: ProposedChangeRepository, proposed_change: InfrahubNode
        ) -> Union[int, pytest.ExitCode]:
            config_file = str(directory / ".infrahub.yml")
            test_directory = directory / "tests"

            if not test_directory.is_dir():
                log.debug(
                    event="repository_tests_ignored",
                    proposed_change=proposed_change,
                    repository=repository.repository_name,
                    message="tests directory not found",
                )
                return 1

            # Redirect stdout/stderr to avoid showing pytest lines in the git agent
            old_out = sys.stdout
            old_err = sys.stderr

            with Path(os.devnull).open(mode="w", encoding="utf-8") as devnull:
                sys.stdout = devnull
                sys.stderr = devnull

                exit_code = pytest.main(
                    [
                        str(test_directory),
                        f"--infrahub-repo-config={config_file}",
                        f"--infrahub-address={config.SETTINGS.main.internal_address}",
                        "-qqqq",
                        "-s",
                    ],
                    plugins=[
                        InfrahubBackendPlugin(service.client.config, repository.repository_id, proposed_change.id)
                    ],
                )

            # Restore stdout/stderr back to their orignal states
            sys.stdout = old_out
            sys.stderr = old_err

            return exit_code

        for repository in message.branch_diff.repositories:
            log_line = "Skipping tests for data only branch"
            if message.source_branch_sync_with_git:
                log_line = "Running tests"
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
                    event="repository_tests_completed",
                    proposed_change=message.proposed_change,
                    repository=repository.repository_name,
                    return_code=return_code,
                )
            await task_report.info(f"{repository.repository_name}: {log_line}")


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


async def _validate_repository_merge_conflicts(repositories: list[ProposedChangeRepository]) -> bool:
    conflicts = False
    for repo in repositories:
        if repo.has_diff and not repo.is_staging:
            git_repo = await InfrahubRepository.init(id=repo.repository_id, name=repo.repository_name)
            async with lock.registry.get(name=repo.repository_name, namespace="repository"):
                repo.conflicts = await git_repo.get_conflicts(
                    source_branch=repo.source_branch, dest_branch=repo.destination_branch
                )
                if repo.conflicts:
                    conflicts = True

    return conflicts


async def _gather_repository_repository_diffs(repositories: list[ProposedChangeRepository]) -> None:
    for repo in repositories:
        if repo.has_diff and repo.source_commit and repo.destination_commit:
            # TODO we need to find a way to return all files in the repo if the repo is new
            git_repo = await InfrahubRepository.init(id=repo.repository_id, name=repo.repository_name)

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


async def _populate_subscribers(branch_diff: ProposedChangeBranchDiff, service: InfrahubServices, branch: str) -> None:
    result = await service.client.execute_graphql(
        query=GATHER_GRAPHQL_QUERY_SUBSCRIBERS,
        branch_name=branch,
        variables={"members": branch_diff.modified_nodes(branch=branch)},
    )

    for group in result[InfrahubKind.GRAPHQLQUERYGROUP]["edges"]:
        for subscriber in group["node"]["subscribers"]["edges"]:
            branch_diff.subscribers.append(
                ProposedChangeSubscriber(subscriber_id=subscriber["node"]["id"], kind=subscriber["node"]["__typename"])
            )


async def _get_proposed_change_schema_integrity_constraints(
    message: messages.RequestProposedChangeSchemaIntegrity, schema: SchemaBranch
) -> list[SchemaUpdateConstraintInfo]:
    node_diff_field_summary_map: dict[str, NodeDiffFieldSummary] = {}
    for node_diff in message.branch_diff.diff_summary:
        node_kind = node_diff["kind"]
        if node_kind not in node_diff_field_summary_map:
            node_diff_field_summary_map[node_kind] = NodeDiffFieldSummary(kind=node_kind)
        field_summary = node_diff_field_summary_map[node_kind]
        for element in node_diff["elements"]:
            element_name = element["name"]
            element_type = element["element_type"]
            if element_type.lower() in (
                DiffElementType.RELATIONSHIP_MANY.value.lower(),
                DiffElementType.RELATIONSHIP_ONE.value.lower(),
            ):
                field_summary.relationship_names.add(element_name)
            elif element_type.lower() in (DiffElementType.ATTRIBUTE.value.lower(),):
                field_summary.attribute_names.add(element_name)

    determiner = ConstraintValidatorDeterminer(schema_branch=schema)
    return await determiner.get_constraints(node_diffs=list(node_diff_field_summary_map.values()))
