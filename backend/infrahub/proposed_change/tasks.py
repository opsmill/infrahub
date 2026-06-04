from __future__ import annotations

import asyncio
import os
import sys
from enum import IntFlag
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.exceptions import ModuleImportError, NodeNotFoundError, URLNotFoundError
from infrahub_sdk.node import InfrahubNode
from infrahub_sdk.protocols import (
    CoreArtifactDefinition,
    CoreArtifactValidator,
    CoreGeneratorDefinition,
    CoreGeneratorValidator,
    CoreProposedChange,
)
from infrahub_sdk.schema.repository import InfrahubGeneratorDefinitionConfig
from prefect import flow, task
from prefect.cache_policies import NONE
from prefect.client.schemas.objects import (
    State,  # noqa: TC002
)
from prefect.logging import get_run_logger
from prefect.states import Completed, Failed
from pydantic import BaseModel

from infrahub import config, lock
from infrahub.artifacts.models import CheckArtifactCreate
from infrahub.context import InfrahubContext  # noqa: TC001  needed for prefect flow
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.branch.tasks import merge_branch
from infrahub.core.constants import (
    CheckType,
    DiffAction,
    GeneratorInstanceStatus,
    InfrahubKind,
    RepositoryInternalStatus,
    ValidatorConclusion,
)
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.model.diff import DiffElementType, SchemaConflict
from infrahub.core.diff.model.path import NodeDiffFieldSummary
from infrahub.core.integrity.object_conflict.conflict_recorder import ObjectConflictValidatorRecorder
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreDataCheck, CoreGenericAccount, CoreValidator
from infrahub.core.protocols import CoreProposedChange as InternalCoreProposedChange
from infrahub.core.timestamp import Timestamp
from infrahub.core.validators.checks_runner import run_checks_and_update_validator
from infrahub.core.validators.determiner import ConstraintValidatorDeterminer
from infrahub.core.validators.models.validate_migration import SchemaValidateMigrationData
from infrahub.core.validators.tasks import schema_validate_migrations
from infrahub.dependencies.registry import get_component_registry
from infrahub.events import EventMeta, ProposedChangeMergedEvent
from infrahub.exceptions import MergeFailedError, SchemaNotFoundError, ValidationError
from infrahub.generators.models import ProposedChangeGeneratorDefinition
from infrahub.git.base import extract_repo_file_information
from infrahub.git.closure_builder.canonicalizer import canonicalize_path
from infrahub.git.models import TriggerRepositoryInternalChecks, TriggerRepositoryUserChecks
from infrahub.git.repository import InfrahubRepository, get_initialized_repo
from infrahub.git.utils import fetch_artifact_definition_targets, fetch_proposed_change_generator_definition_targets
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.execution import cached_parse
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.log import get_logger
from infrahub.message_bus.types import (
    ProposedChangeArtifactDefinition,
    ProposedChangeBranchDiff,
    ProposedChangeRepository,
    ProposedChangeSubscriber,
)
from infrahub.proposed_change.branch_diff import (
    GitRepositoryFileDiffer,
    get_modified_node_ids,
    has_data_changes,
    has_node_changes,
    populate_repository_file_diffs,
    set_diff_summary_cache,
)
from infrahub.proposed_change.constants import ProposedChangeState
from infrahub.proposed_change.models import (
    RequestArtifactDefinitionCheck,
    RequestGeneratorDefinitionCheck,
    RequestProposedChangeDataIntegrity,
    RequestProposedChangePipeline,
    RequestProposedChangeRefreshArtifacts,
    RequestProposedChangeRepositoryChecks,
    RequestProposedChangeRunGenerators,
    RequestProposedChangeSchemaIntegrity,
    RequestProposedChangeUserTests,
    RunGeneratorAsCheckModel,
)
from infrahub.pytest_plugin import InfrahubBackendPlugin
from infrahub.validators.tasks import start_validator
from infrahub.workers.dependencies import get_cache, get_client, get_database, get_event_service, get_workflow
from infrahub.workflows.catalogue import (
    GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE,
    GIT_REPOSITORY_INTERNAL_CHECKS_TRIGGER,
    GIT_REPOSITORY_USER_CHECKS_TRIGGER,
    REQUEST_ARTIFACT_DEFINITION_CHECK,
    REQUEST_GENERATOR_DEFINITION_CHECK,
    REQUEST_PROPOSED_CHANGE_DATA_INTEGRITY,
    REQUEST_PROPOSED_CHANGE_REFRESH_ARTIFACTS,
    REQUEST_PROPOSED_CHANGE_REPOSITORY_CHECKS,
    REQUEST_PROPOSED_CHANGE_RUN_GENERATORS,
    REQUEST_PROPOSED_CHANGE_SCHEMA_INTEGRITY,
    REQUEST_PROPOSED_CHANGE_USER_TESTS,
    RUN_GENERATOR_AS_CHECK,
)
from infrahub.workflows.utils import add_tags

from .branch_diff import get_diff_summary_cache, get_modified_kinds
from .checker import verify_proposed_change_is_mergeable

if TYPE_CHECKING:
    import logging

    from infrahub_sdk.client import InfrahubClient
    from infrahub_sdk.diff import NodeDiff

    from infrahub.core.models import SchemaUpdateConstraintInfo
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


async def _proposed_change_transition_state(
    state: ProposedChangeState,
    database: InfrahubDatabase,
    user_id: str,
    proposed_change: InternalCoreProposedChange | None = None,
    proposed_change_id: str | None = None,
) -> None:
    async with database.start_session() as db:
        if proposed_change is None and proposed_change_id:
            proposed_change = await registry.manager.get_one(
                db=db, id=proposed_change_id, kind=InternalCoreProposedChange, raise_on_error=True
            )
        if proposed_change:
            proposed_change.state.value = state.value  # type: ignore[misc]
            await proposed_change.save(db=db, user_id=user_id)


# async def proposed_change_transition_merged(flow: Flow, flow_run: FlowRun, state: State) -> None:
#     await _proposed_change_transition_state(
#         proposed_change_id=flow_run.parameters["proposed_change_id"], state=ProposedChangeState.MERGED
#     )


# async def proposed_change_transition_open(flow: Flow, flow_run: FlowRun, state: State) -> None:
#     await _proposed_change_transition_state(
#         proposed_change_id=flow_run.parameters["proposed_change_id"], state=ProposedChangeState.OPEN
#     )


@flow(
    name="proposed-change-merge",
    flow_run_name="Merge propose change: {proposed_change_name} ",
    description="Merge a given proposed change.",
    # TODO need to investigate why these function are not working as expected
    # on_completion=[proposed_change_transition_merged],  # type: ignore
    # on_failure=[proposed_change_transition_open],  # type: ignore
    # on_crashed=[proposed_change_transition_open],  # type: ignore
    # on_cancellation=[proposed_change_transition_open],  # type: ignore
)
async def merge_proposed_change(
    proposed_change_id: str,
    proposed_change_name: str,  # noqa: ARG001
    context: InfrahubContext,
) -> State:
    log = get_run_logger()
    await add_tags(nodes=[proposed_change_id])
    database = await get_database()

    async with database.start_session() as db:
        proposed_change = await registry.manager.get_one(
            db=db,
            id=proposed_change_id,
            kind=InternalCoreProposedChange,
            raise_on_error=True,
            prefetch_relationships=True,
        )
        log.info("Validating if all conditions are met to merge the proposed change")

        try:
            await verify_proposed_change_is_mergeable(
                proposed_change=proposed_change,  # type: ignore[arg-type]
                db=db,
                account_session=context.account,
            )
        except ValueError as exc:
            await _proposed_change_transition_state(
                proposed_change=proposed_change,
                state=ProposedChangeState.OPEN,
                database=db,
                user_id=context.account.account_id,
            )
            return Failed(message=str(exc))

        source_branch = await Branch.get_by_name(db=db, name=proposed_change.source_branch.value)
        validations = await proposed_change.validations.get_peers(db=db, peer_type=CoreValidator)
        for validation in validations.values():
            validator_kind = validation.get_kind()
            if (
                validator_kind != InfrahubKind.DATAVALIDATOR
                and validation.conclusion.value.value != ValidatorConclusion.SUCCESS.value
            ):
                # Ignoring Data integrity checks as they are handled again later
                await _proposed_change_transition_state(
                    proposed_change=proposed_change,
                    state=ProposedChangeState.OPEN,
                    database=db,
                    user_id=context.account.account_id,
                )
                return Failed(message="Unable to merge proposed change containing failing checks")
            if validator_kind == InfrahubKind.DATAVALIDATOR:
                data_checks = await validation.checks.get_peers(db=db, peer_type=CoreDataCheck)
                for check in data_checks.values():
                    if check.conflicts.value and not check.keep_branch.value:
                        await _proposed_change_transition_state(
                            proposed_change=proposed_change,
                            state=ProposedChangeState.OPEN,
                            database=db,
                            user_id=context.account.account_id,
                        )
                        return Failed(
                            message="Data conflicts found on branch and missing decisions about what branch to keep"
                        )

        log.info("Proposed change is eligible to be merged")

        merge_succeeded = False
        try:
            await merge_branch(branch=source_branch.name, context=context, proposed_change_id=proposed_change_id)
            merge_succeeded = True
        except MergeFailedError as exc:
            return Failed(message=exc.message)
        except Exception as exc:
            log.exception("Unexpected failure during proposed change merge")
            return Failed(message=f"Merge failure when trying to merge {source_branch.name}: {exc}")
        except BaseException as exc:
            log.exception("Unexpected failure during proposed change merge")
            raise exc
        finally:
            if not merge_succeeded:
                await _proposed_change_transition_state(
                    proposed_change=proposed_change,
                    state=ProposedChangeState.OPEN,
                    database=db,
                    user_id=context.account.account_id,
                )

        log.info(f"Branch {source_branch.name} has been merged successfully")

        await _proposed_change_transition_state(
            proposed_change=proposed_change,
            state=ProposedChangeState.MERGED,
            database=db,
            user_id=context.account.account_id,
        )

        current_user = await NodeManager.get_one_by_id_or_default_filter(
            id=context.account.account_id, kind=CoreGenericAccount, db=db
        )
        event_context = context.to_event_context()
        event_service = await get_event_service()
        await event_service.send(
            event=ProposedChangeMergedEvent(
                proposed_change_id=proposed_change.id,
                proposed_change_name=proposed_change.name.value,
                proposed_change_state=proposed_change.state.value,
                merged_by_account_id=current_user.id,
                merged_by_account_name=current_user.name.value,
                meta=EventMeta.from_context(context=event_context),
            )
        )

        return Completed(message="proposed change merged successfully")


@flow(
    name="proposed-changes-cancel-branch",
    flow_run_name="Cancel all proposed change associated with branch {branch_name}",
    description="Cancel all Proposed change associated with a branch.",
)
async def cancel_proposed_changes_branch(branch_name: str) -> None:
    await add_tags(branches=[branch_name])

    client = get_client()

    proposed_changed_opened = await client.filters(
        kind=CoreProposedChange,
        include=["id", "source_branch"],
        state__value=ProposedChangeState.OPEN.value,
        source_branch__value=branch_name,
    )
    proposed_changed_closed = await client.filters(
        kind=CoreProposedChange,
        include=["id", "source_branch"],
        state__value=ProposedChangeState.CLOSED.value,
        source_branch__value=branch_name,
    )

    for proposed_change in proposed_changed_opened + proposed_changed_closed:
        await cancel_proposed_change(proposed_change=proposed_change, client=get_client())


@task(name="Cancel a proposed change", description="Cancel a proposed change", cache_policy=NONE)  # type: ignore[arg-type]
async def cancel_proposed_change(proposed_change: CoreProposedChange, client: InfrahubClient) -> None:
    await add_tags(nodes=[proposed_change.id])
    log = get_run_logger()

    log.info("Canceling proposed change as the source branch was deleted")
    proposed_change = await client.get(kind=CoreProposedChange, id=proposed_change.id)
    proposed_change.state.value = ProposedChangeState.CANCELED.value
    await proposed_change.save()


@flow(name="proposed-changed-data-integrity", flow_run_name="Triggers data integrity check")
async def run_proposed_change_data_integrity_check(model: RequestProposedChangeDataIntegrity) -> None:
    """Triggers a data integrity validation check on the provided proposed change to start."""
    await add_tags(branches=[model.source_branch], nodes=[model.proposed_change])

    database = await get_database()
    async with database.start_session() as dbs:
        destination_branch = await registry.get_branch(db=dbs, branch=model.destination_branch)
        source_branch = await registry.get_branch(db=dbs, branch=model.source_branch)
        component_registry = get_component_registry()

        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=dbs, branch=source_branch)
        diff_coordinator.set_logger(get_run_logger())
        await diff_coordinator.update_branch_diff(
            base_branch=destination_branch, diff_branch=source_branch, proposed_change_id=model.proposed_change
        )


@flow(name="proposed-changed-run-generator", flow_run_name="Run generators")
async def run_generators(model: RequestProposedChangeRunGenerators, context: InfrahubContext) -> None:
    await add_tags(branches=[model.source_branch], nodes=[model.proposed_change], db_change=True)

    client = get_client()

    generators = await client.filters(
        kind=CoreGeneratorDefinition,
        prefetch_relationships=True,
        populate_store=True,
        branch=model.source_branch,
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
            execute_in_proposed_change=generator.execute_in_proposed_change.value,
            execute_after_merge=generator.execute_after_merge.value,
        )
        for generator in generators
        if generator.execute_in_proposed_change.value
    ]

    diff_summary = await get_diff_summary_cache(pipeline_id=model.branch_diff.pipeline_id)
    modified_kinds = get_modified_kinds(diff_summary=diff_summary, branch=model.source_branch)

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
            condition=model.source_branch_sync_with_git and model.branch_diff.has_file_modifications,
        )

        for changed_model in modified_kinds:
            select = select.add_flag(
                current=select,
                flag=DefinitionSelect.MODIFIED_KINDS,
                condition=changed_model in generator_definition.query_models,
            )

        if select:
            request_generator_def_check_model = RequestGeneratorDefinitionCheck(
                generator_definition=generator_definition,
                branch_diff=model.branch_diff,
                proposed_change=model.proposed_change,
                source_branch=model.source_branch,
                source_branch_sync_with_git=model.source_branch_sync_with_git,
                destination_branch=model.destination_branch,
            )
            await get_workflow().submit_workflow(
                workflow=REQUEST_GENERATOR_DEFINITION_CHECK,
                parameters={"model": request_generator_def_check_model},
                context=context,
            )

    if model.refresh_artifacts:
        request_refresh_artifact_model = RequestProposedChangeRefreshArtifacts(
            proposed_change=model.proposed_change,
            source_branch=model.source_branch,
            source_branch_sync_with_git=model.source_branch_sync_with_git,
            destination_branch=model.destination_branch,
            branch_diff=model.branch_diff,
        )
        await get_workflow().submit_workflow(
            workflow=REQUEST_PROPOSED_CHANGE_REFRESH_ARTIFACTS,
            parameters={"model": request_refresh_artifact_model},
            context=context,
        )

    if model.do_repository_checks:
        model_proposed_change_repo_checks = RequestProposedChangeRepositoryChecks(
            proposed_change=model.proposed_change,
            source_branch=model.source_branch,
            source_branch_sync_with_git=model.source_branch_sync_with_git,
            destination_branch=model.destination_branch,
            branch_diff=model.branch_diff,
        )
        await get_workflow().submit_workflow(
            workflow=REQUEST_PROPOSED_CHANGE_REPOSITORY_CHECKS,
            context=context,
            parameters={"model": model_proposed_change_repo_checks},
        )


@flow(name="proposed-changed-schema-integrity", flow_run_name="Process schema integrity")
async def run_proposed_change_schema_integrity_check(model: RequestProposedChangeSchemaIntegrity) -> None:
    # For now, we retrieve the latest schema for each branch from the registry
    # In the future it would be good to generate the object SchemaUpdateValidationResult from message.branch_diff
    await add_tags(branches=[model.source_branch], nodes=[model.proposed_change])

    source_schema = registry.schema.get_schema_branch(name=model.source_branch).duplicate()
    dest_schema = registry.schema.get_schema_branch(name=model.destination_branch).duplicate()

    candidate_schema = dest_schema.duplicate()
    candidate_schema.update(schema=source_schema)

    try:
        candidate_schema.duplicate().process()
    except (ValueError, ValidationError, SchemaNotFoundError) as exc:
        error_msg = str(exc)
        parts = error_msg.split(":", 1)
        kind = parts[0].strip() if len(parts) > 1 and parts[0].strip() else "Unknown"
        schema_path = f"schema/{kind}"
        database = await get_database()
        async with database.start_transaction() as db:
            object_conflict_validator_recorder = ObjectConflictValidatorRecorder(
                db=db,
                validator_kind=InfrahubKind.SCHEMAVALIDATOR,
                validator_label="Schema Integrity",
                check_schema_kind=InfrahubKind.SCHEMACHECK,
            )
            await object_conflict_validator_recorder.record_conflicts(
                proposed_change_id=model.proposed_change,
                conflicts=[
                    SchemaConflict(
                        name=schema_path,
                        type="schema.process.validation",
                        kind=kind,
                        id=schema_path,
                        path=schema_path,
                        value=error_msg,
                        branch=model.source_branch,
                    )
                ],
            )
        return

    schema_diff = dest_schema.diff(other=candidate_schema)
    validation_result = dest_schema.validate_update(other=candidate_schema, diff=schema_diff)

    diff_summary = await get_diff_summary_cache(pipeline_id=model.branch_diff.pipeline_id)
    constraints_from_data_diff = await _get_proposed_change_schema_integrity_constraints(
        schema=candidate_schema, diff_summary=diff_summary
    )
    constraints_from_schema_diff = validation_result.constraints
    constraints = set(constraints_from_data_diff + constraints_from_schema_diff)

    if not constraints:
        return

    # ----------------------------------------------------------
    # Validate if the new schema is valid with the content of the database
    # ----------------------------------------------------------
    source_branch = registry.get_branch_from_registry(branch=model.source_branch)
    responses = await schema_validate_migrations(
        message=SchemaValidateMigrationData(
            branch=source_branch, schema_branch=candidate_schema, constraints=list(constraints)
        )
    )

    # TODO we need to report a failure if an error happened during the execution of a validator
    conflicts: list[SchemaConflict] = []
    for response in responses:
        for violation in response.violations:
            conflicts.append(
                SchemaConflict(
                    name=response.schema_path.get_path(),
                    type=response.constraint_name,
                    kind=violation.node_kind,
                    id=violation.node_id,
                    path=response.schema_path.get_path(),
                    value=violation.message,
                    branch="placeholder",
                )
            )

    database = await get_database()
    async with database.start_transaction() as db:
        object_conflict_validator_recorder = ObjectConflictValidatorRecorder(
            db=db,
            validator_kind=InfrahubKind.SCHEMAVALIDATOR,
            validator_label="Schema Integrity",
            check_schema_kind=InfrahubKind.SCHEMACHECK,
        )
        await object_conflict_validator_recorder.record_conflicts(
            proposed_change_id=model.proposed_change, conflicts=conflicts
        )


async def _get_proposed_change_schema_integrity_constraints(
    schema: SchemaBranch, diff_summary: list[NodeDiff]
) -> list[SchemaUpdateConstraintInfo]:
    node_diff_field_summary_map: dict[str, NodeDiffFieldSummary] = {}

    for node_diff in diff_summary:
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
            elif element_type.lower() == DiffElementType.ATTRIBUTE.value.lower():
                field_summary.attribute_names.add(element_name)

    determiner = ConstraintValidatorDeterminer(schema_branch=schema)
    return await determiner.get_constraints(node_diffs=list(node_diff_field_summary_map.values()))


@flow(name="proposed-changed-repository-checks", flow_run_name="Process user defined checks")
async def repository_checks(model: RequestProposedChangeRepositoryChecks, context: InfrahubContext) -> None:
    await add_tags(branches=[model.source_branch], nodes=[model.proposed_change])

    for repository in model.branch_diff.repositories:
        if (
            model.source_branch_sync_with_git
            and not repository.read_only
            and repository.internal_status == RepositoryInternalStatus.ACTIVE.value
        ):
            trigger_internal_checks_model = TriggerRepositoryInternalChecks(
                proposed_change=model.proposed_change,
                repository=repository.repository_id,
                source_branch=model.source_branch,
                target_branch=model.destination_branch,
            )
            await get_workflow().submit_workflow(
                workflow=GIT_REPOSITORY_INTERNAL_CHECKS_TRIGGER,
                context=context,
                parameters={"model": trigger_internal_checks_model},
            )

        trigger_user_checks_model = TriggerRepositoryUserChecks(
            proposed_change=model.proposed_change,
            repository_id=repository.repository_id,
            repository_name=repository.repository_name,
            source_branch=model.source_branch,
            source_branch_sync_with_git=model.source_branch_sync_with_git,
            target_branch=model.destination_branch,
            branch_diff=model.branch_diff,
        )
        await get_workflow().submit_workflow(
            workflow=GIT_REPOSITORY_USER_CHECKS_TRIGGER,
            context=context,
            parameters={"model": trigger_user_checks_model},
        )


@flow(name="proposed-changed-user-tests", flow_run_name="Run unit tests in repositories")
async def run_proposed_change_user_tests(model: RequestProposedChangeUserTests) -> None:
    await add_tags(branches=[model.source_branch], nodes=[model.proposed_change])

    log = get_run_logger()
    client = get_client()

    try:
        proposed_change = await client.get(kind=CoreProposedChange, id=model.proposed_change)
    except NodeNotFoundError:
        log.warning(f"Proposed change ({model.proposed_change}) not found, skipping user tests execution")
        return

    def _execute(
        directory: Path, repository: ProposedChangeRepository, proposed_change: InfrahubNode
    ) -> int | pytest.ExitCode:
        # Check for both .infrahub.yml and .infrahub.yaml, prefer .yml if both exist
        config_file_yml = directory / ".infrahub.yml"
        config_file_yaml = directory / ".infrahub.yaml"

        if config_file_yml.is_file():
            config_file = str(config_file_yml)
        elif config_file_yaml.is_file():
            config_file = str(config_file_yaml)
        else:
            config_file = str(config_file_yml)  # Default to .yml for error messages
        test_directory = directory / "tests"
        log = get_logger()

        if not test_directory.is_dir():
            log.debug(
                event="repository_tests_ignored",
                proposed_change=proposed_change,
                repository=repository.repository_name,
                message="tests directory not found",
            )
            return 1

        # Check if config file exists and log error if neither extension is found
        if not config_file_yml.is_file() and not config_file_yaml.is_file():
            log.error(
                event="repository_tests_failed",
                proposed_change=proposed_change,
                repository=repository.repository_name,
                message="Configuration file not found (.infrahub.yml or .infrahub.yaml)",
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
                plugins=[InfrahubBackendPlugin(client.config, repository.repository_id, proposed_change.id)],
            )

        # Restore stdout/stderr back to their orignal states
        sys.stdout = old_out
        sys.stderr = old_err

        return exit_code

    for repository in model.branch_diff.repositories:
        if model.source_branch_sync_with_git:
            repo = await get_initialized_repo(
                client=client,
                repository_id=repository.repository_id,
                name=repository.repository_name,
                repository_kind=repository.kind,
            )
            commit = repo.get_commit_value(proposed_change.source_branch.value)
            worktree_directory = Path(repo.get_commit_worktree(commit=commit).directory)

            return_code = await asyncio.to_thread(_execute, worktree_directory, repository, proposed_change)
            log.info(msg=f"repository_tests_completed return_code={return_code}")


@flow(
    name="artifacts-generation-validation",
    flow_run_name="Validating generation of artifacts for {model.artifact_definition.definition_name}",
)
async def validate_artifacts_generation(model: RequestArtifactDefinitionCheck, context: InfrahubContext) -> None:
    await add_tags(branches=[model.source_branch], nodes=[model.proposed_change], db_change=True)

    log = get_run_logger()
    client = get_client()
    client.request_context = context.to_request_context()

    artifact_definition = await client.get(
        kind=CoreArtifactDefinition,
        id=model.artifact_definition.definition_id,
        branch=model.source_branch,
    )
    proposed_change = await client.get(kind=InfrahubKind.PROPOSEDCHANGE, id=model.proposed_change)

    validator_name = f"Artifact Validator: {model.artifact_definition.definition_name}"

    await proposed_change.validations.fetch()

    previous_validator: CoreArtifactValidator | None = None
    for relationship in proposed_change.validations.peers:
        existing_validator = relationship.peer
        if (
            existing_validator.typename == InfrahubKind.ARTIFACTVALIDATOR
            and existing_validator.definition.id == model.artifact_definition.definition_id
        ):
            previous_validator = existing_validator

    validator = await start_validator(
        client=client,
        validator=previous_validator,
        validator_type=CoreArtifactValidator,
        proposed_change=model.proposed_change,
        data={
            "label": validator_name,
            "definition": model.artifact_definition.definition_id,
        },
        context=context,
    )

    # Needs to be fetched before fetching group members otherwise `object` relationship would override
    # existing node in client store without the `name` attribute due to #521
    existing_artifacts = await client.filters(
        kind=InfrahubKind.ARTIFACT,
        definition__ids=[model.artifact_definition.definition_id],
        include=["object"],
        branch=model.source_branch,
    )

    group = await fetch_artifact_definition_targets(
        client=client, branch=model.source_branch, definition=artifact_definition
    )

    artifacts_by_member = _map_artifacts_by_member(
        existing_artifacts=existing_artifacts,
        definition_name=model.artifact_definition.definition_name,
        log=log,
    )

    repository = model.branch_diff.get_repository(repository_id=model.artifact_definition.repository_id)

    source_schema_branch = registry.schema.get_schema_branch(name=model.source_branch)
    source_branch = registry.get_branch_from_registry(branch=model.source_branch)

    graphql_params = await prepare_graphql_params(db=await get_database(), branch=model.source_branch)
    query_analyzer = InfrahubGraphQLQueryAnalyzer(
        query=model.artifact_definition.query_payload,
        branch=source_branch,
        schema_branch=source_schema_branch,
        schema=graphql_params.schema,
        document=cached_parse(model.artifact_definition.query_payload),
    )

    # only_has_unique_targets is True when the query is guaranteed to return results
    # for a specific set of nodes — e.g. it uses an `ids` argument or a uniqueness
    # constraint. When False, the query may return any number of nodes and we cannot
    # map a changed node back to a specific artifact without re-running every target.
    only_has_unique_targets = query_analyzer.query_report.only_has_unique_targets

    # Collect the IDs of nodes whose changes are actually relevant to this query.
    # A change is relevant only when at least one field that was modified is also
    # read by the query. This lets us skip regeneration when, for example, only a
    # `description` field changed but the query only reads `name` and `color`.
    diff_summary = await get_diff_summary_cache(pipeline_id=model.branch_diff.pipeline_id)
    relevant_node_changes = []
    for node_diff in diff_summary:
        if (
            node_diff["branch"] == model.source_branch
            and node_diff["kind"] in query_analyzer.query_report.requested_read
        ):
            updated_fields = {element["name"] for element in node_diff["elements"]}
            relevant_fields = set(query_analyzer.query_report.fields_by_kind(node_diff["kind"]))
            if updated_fields & relevant_fields:
                relevant_node_changes.append(node_diff["id"])

    if only_has_unique_targets:
        # The query targets specific nodes by ID or unique constraint, so we can
        # look up exactly which artifacts are linked to the changed nodes and limit
        # regeneration to only those artifacts.
        subscribers = await _get_subscribers_for_nodes(
            node_ids=relevant_node_changes, branch=model.source_branch, client=client
        )
        impacted_artifacts = [
            subscriber.subscriber_id for subscriber in subscribers if subscriber.kind == InfrahubKind.ARTIFACT
        ]
    elif relevant_node_changes:
        # The query does not guarantee unique targets, so we cannot determine which
        # specific artifacts are affected. At least one relevant field changed, so we
        # must fall back to regenerating all artifacts for this definition to be safe.
        impacted_artifacts = list(artifacts_by_member.values())
        log.warning(
            f"Artifact definition {artifact_definition.name.value} query does not guarantee unique targets. All targets will be processed."
        )
    else:
        # No node of a queried kind had any of its queried fields modified, so no
        # artifact can be stale regardless of query targeting capability.
        impacted_artifacts = []
        log.info(
            f"Artifact definition {artifact_definition.name.value} has no applicable node changes. Existing artifacts will not be re-rendered."
        )

    repo_diff_for_definition = _repo_diff_or_none(
        branch_diff=model.branch_diff, repository_id=model.artifact_definition.repository_id
    )
    managed_branch = (
        _query_changed(definition=model.artifact_definition, diff_summary=diff_summary)
        or _definition_changed(definition=model.artifact_definition, diff_summary=diff_summary)
        or (
            repo_diff_for_definition is not None
            and _transform_changed(definition=model.artifact_definition, repo_diff=repo_diff_for_definition)
        )
    )
    if managed_branch:
        log.info("Query, definition or repository file change detected, all artifacts will be processed")

    checks = []

    for relationship in group.members.peers:
        member = relationship.peer
        artifact_id = artifacts_by_member.get(member.id)
        if _should_render_artifact(
            artifact_id=artifact_id,
            managed_branch=managed_branch,
            impacted_artifacts=impacted_artifacts,
        ):
            log.info(f"Trigger Artifact processing for {member.display_label}")

            check_model = CheckArtifactCreate(
                context=context,
                artifact_name=model.artifact_definition.artifact_name,
                artifact_id=artifact_id,
                artifact_definition=model.artifact_definition.definition_id,
                artifact_definition_name=model.artifact_definition.definition_name,
                commit=repository.source_commit,
                content_type=model.artifact_definition.content_type,
                transform_type=model.artifact_definition.transform_kind,
                transform_location=model.artifact_definition.transform_location,
                convert_query_response=model.artifact_definition.convert_query_response,
                repository_id=repository.repository_id,
                repository_name=repository.repository_name,
                repository_kind=repository.kind,
                branch_name=model.source_branch,
                query=model.artifact_definition.query_name,
                query_id=model.artifact_definition.query_id,
                variables=await member.extract(params=artifact_definition.parameters.value),
                target_id=member.id,
                target_kind=member.get_kind(),
                target_name=member.display_label,
                timeout=model.artifact_definition.timeout,
                validator_id=validator.id,
            )

            checks.append(
                get_workflow().execute_workflow(
                    workflow=GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE,
                    parameters={"model": check_model},
                    expected_return=ValidatorConclusion,
                )
            )

    await run_checks_and_update_validator(
        event_service=await get_event_service(),
        checks=checks,
        validator=validator,
        proposed_change_id=model.proposed_change,
        context=context,
    )


def _map_artifacts_by_member(
    existing_artifacts: list[InfrahubNode],
    definition_name: str,
    log: logging.Logger | logging.LoggerAdapter,
) -> dict[str, str]:
    """Map each member id to its existing artifact id, skipping artifacts whose.

    `object` peer cannot be resolved. Such orphan rows can appear when a target
    node has been removed via a path that does not cascade-delete artifacts.

    """
    artifacts_by_member: dict[str, str] = {}
    for artifact in existing_artifacts:
        object_id = artifact.object.id
        if object_id is None:
            log.warning(
                f"Skipping orphan artifact {artifact.id} for definition {definition_name}: object peer unresolvable"
            )
            continue
        artifacts_by_member[object_id] = artifact.id
    return artifacts_by_member


def _should_render_artifact(
    artifact_id: str | None,
    managed_branch: bool,
    impacted_artifacts: list[str],
) -> bool:
    """Returns a boolean to indicate if an artifact should be generated or not.

    Will return true if:
        * The artifact_id wasn't set which could be that it's a new object that doesn't have a previous artifact
        * The source branch is synced with git and has file modifications (managed_branch)
        * The artifact_id exists in the impacted_artifacts list
    Will return false if:
        * The artifact_id exists and is not in the impacted list.
    """
    if not artifact_id or managed_branch:
        return True

    return artifact_id in impacted_artifacts


@flow(
    name="run-generator-as-check",
    flow_run_name="Execute Generator {model.generator_definition.definition_name} for {model.target_name}",
)
async def run_generator_as_check(model: RunGeneratorAsCheckModel, context: InfrahubContext) -> ValidatorConclusion:
    await add_tags(branches=[model.branch_name], nodes=[model.proposed_change], db_change=True)

    client = get_client()
    client.request_context = context.to_request_context()
    log = get_run_logger()

    repository = await get_initialized_repo(
        client=client,
        repository_id=model.repository_id,
        name=model.repository_name,
        repository_kind=model.repository_kind,
        commit=model.commit,
    )

    conclusion = ValidatorConclusion.SUCCESS

    generator_definition = InfrahubGeneratorDefinitionConfig(
        name=model.generator_definition.definition_name,
        class_name=model.generator_definition.class_name,
        file_path=model.generator_definition.file_path,
        query=model.generator_definition.query_name,
        targets=model.generator_definition.group_id,
        convert_query_response=model.generator_definition.convert_query_response,
        execute_in_proposed_change=model.generator_definition.execute_in_proposed_change,
        execute_after_merge=model.generator_definition.execute_after_merge,
    )

    commit_worktree = repository.get_commit_worktree(commit=model.commit)

    file_info = extract_repo_file_information(
        full_filename=commit_worktree.directory / generator_definition.file_path,
        repo_directory=repository.directory_root,
        worktree_directory=commit_worktree.directory,
    )
    generator_instance = await _define_instance(model=model, client=client)

    check_message = "Instance successfully generated"
    try:
        log.debug(f"repo information {file_info}")
        log.debug(f"Root directory : {repository.directory_root}")
        generator_class = generator_definition.load_class(
            import_root=repository.directory_root, relative_path=file_info.relative_repo_path_dir
        )

        generator = generator_class(
            query=generator_definition.query,
            client=client,
            branch=model.branch_name,
            params=model.variables,
            generator_instance=generator_instance.id,
            convert_query_response=generator_definition.convert_query_response,
            execute_after_merge=generator_definition.execute_after_merge,
            execute_in_proposed_change=generator_definition.execute_in_proposed_change,
            infrahub_node=InfrahubNode,
        )
        generator._init_client.request_context = context.to_request_context()
        await generator.run(identifier=generator_definition.name)
        generator_instance.status.value = GeneratorInstanceStatus.READY.value
    except ModuleImportError as exc:
        conclusion = ValidatorConclusion.FAILURE
        generator_instance.status.value = GeneratorInstanceStatus.ERROR.value
        check_message = f"Failed to import generator: {exc.message}"
        log.exception(check_message, exc_info=exc)
    except Exception as exc:
        conclusion = ValidatorConclusion.FAILURE
        generator_instance.status.value = GeneratorInstanceStatus.ERROR.value
        check_message = f"Failed to execute generator: {str(exc)}"
        log.exception(check_message, exc_info=exc)

    log.info("Generator run completed, starting update")
    await generator_instance.update(do_full_update=True)

    check = None
    existing_check = await client.filters(
        kind=InfrahubKind.GENERATORCHECK, validator__ids=model.validator_id, instance__value=generator_instance.id
    )
    if existing_check:
        check = existing_check[0]

    if check:
        check.created_at.value = Timestamp().to_string()
        check.conclusion.value = conclusion.value
        await check.save(request_context=context.to_request_context())
    else:
        check = await client.create(
            kind=InfrahubKind.GENERATORCHECK,
            data={
                "name": model.target_name,
                "origin": model.repository_id,
                "kind": "GeneratorDefinition",
                "validator": model.validator_id,
                "created_at": Timestamp().to_string(),
                "message": check_message,
                "conclusion": conclusion.value,
                "instance": generator_instance.id,
            },
        )
        await check.save()

    return conclusion


async def _define_instance(model: RunGeneratorAsCheckModel, client: InfrahubClient) -> InfrahubNode:
    if model.generator_instance:
        instance = await client.get(
            kind=InfrahubKind.GENERATORINSTANCE, id=model.generator_instance, branch=model.branch_name
        )
        instance.status.value = GeneratorInstanceStatus.PENDING.value
        await instance.update(do_full_update=True)

    else:
        async with lock.registry.get(
            f"{model.target_id}-{model.generator_definition.definition_id}", namespace="generator"
        ):
            instances = await client.filters(
                kind=InfrahubKind.GENERATORINSTANCE,
                definition__ids=[model.generator_definition.definition_id],
                object__ids=[model.target_id],
                branch=model.branch_name,
            )
            if instances:
                instance = instances[0]
                instance.status.value = GeneratorInstanceStatus.PENDING.value
                await instance.update(do_full_update=True)
            else:
                instance = await client.create(
                    kind=InfrahubKind.GENERATORINSTANCE,
                    branch=model.branch_name,
                    data={
                        "name": f"{model.generator_definition.definition_name}: {model.target_name}",
                        "status": GeneratorInstanceStatus.PENDING.value,
                        "object": model.target_id,
                        "definition": model.generator_definition.definition_id,
                    },
                )
                await instance.save()
    return instance


@flow(
    name="request-generator-definition-check",
    flow_run_name="Validate Generator selection for {model.generator_definition.definition_name}",
)
async def request_generator_definition_check(model: RequestGeneratorDefinitionCheck, context: InfrahubContext) -> None:
    await add_tags(branches=[model.source_branch], nodes=[model.proposed_change])

    log = get_run_logger()
    client = get_client()
    client.request_context = context.to_request_context()

    proposed_change = await client.get(kind=InfrahubKind.PROPOSEDCHANGE, id=model.proposed_change)

    validator_name = f"Generator Validator: {model.generator_definition.definition_name}"
    await proposed_change.validations.fetch()

    previous_validator: CoreGeneratorValidator | None = None
    for relationship in proposed_change.validations.peers:
        existing_validator = relationship.peer
        if (
            existing_validator.typename == InfrahubKind.GENERATORVALIDATOR
            and existing_validator.definition.id == model.generator_definition.definition_id
        ):
            previous_validator = existing_validator

    validator = await start_validator(
        client=client,
        validator=previous_validator,
        validator_type=CoreGeneratorValidator,
        proposed_change=model.proposed_change,
        data={
            "label": validator_name,
            "definition": model.generator_definition.definition_id,
        },
        context=context,
    )

    # Needs to be fetched before fetching group members otherwise `object` relationship would override
    # existing node in client store without the `name` attribute due to #521
    existing_instances = await client.filters(
        kind=InfrahubKind.GENERATORINSTANCE,
        definition__ids=[model.generator_definition.definition_id],
        include=["object"],
        branch=model.source_branch,
    )

    group = await fetch_proposed_change_generator_definition_targets(
        client=client, branch=model.source_branch, definition=model.generator_definition
    )

    instance_by_member = {}
    for instance in existing_instances:
        instance_by_member[instance.object.peer.id] = instance.id

    repository = model.branch_diff.get_repository(repository_id=model.generator_definition.repository_id)
    requested_instances = 0
    impacted_instances = model.branch_diff.get_subscribers_ids(kind=InfrahubKind.GENERATORINSTANCE)

    check_generator_run_models: list[RunGeneratorAsCheckModel] = []
    for relationship in group.members.peers:
        member = relationship.peer
        generator_instance = instance_by_member.get(member.id)
        if _run_generator(
            instance_id=generator_instance,
            managed_branch=model.source_branch_sync_with_git,
            impacted_instances=impacted_instances,
        ):
            requested_instances += 1
            log.info(f"Trigger execution of {model.generator_definition.definition_name} for {member.display_label}")
            check_generator_run_model = RunGeneratorAsCheckModel(
                generator_definition=model.generator_definition,
                generator_instance=generator_instance,
                commit=repository.source_commit,
                repository_id=repository.repository_id,
                repository_name=repository.repository_name,
                repository_kind=repository.kind,
                branch_name=model.source_branch,
                query=model.generator_definition.query_name,
                variables=await member.extract(params=model.generator_definition.parameters),
                target_id=member.id,
                target_name=member.display_label,
                validator_id=validator.id,
                proposed_change=model.proposed_change,
            )
            check_generator_run_models.append(check_generator_run_model)

    checks_coroutines = [
        get_workflow().execute_workflow(
            workflow=RUN_GENERATOR_AS_CHECK,
            parameters={"model": check_generator_run_model},
            expected_return=ValidatorConclusion,
            context=context,
        )
        for check_generator_run_model in check_generator_run_models
        if check_generator_run_model.generator_definition.execute_in_proposed_change
    ]

    await run_checks_and_update_validator(
        event_service=await get_event_service(),
        checks=checks_coroutines,
        validator=validator,
        context=context,
        proposed_change_id=proposed_change.id,
    )


def _run_generator(instance_id: str | None, managed_branch: bool, impacted_instances: list[str]) -> bool:
    """Returns a boolean to indicate if a generator instance needs to be executed.

    Will return true if:
        * The instance_id wasn't set which could be that it's a new object that doesn't have a previous generator instance
        * The source branch is set to sync with Git which would indicate that it could contain updates in git to the generator
        * The instance_id exists in the impacted_instances list
    Will return false if:
        * The source branch is a not one that syncs with git and the instance_id exists and is not in the impacted list.

    """
    if not instance_id or managed_branch:
        return True
    return instance_id in impacted_instances


_TRIGGERING_DIFF_ACTIONS = {DiffAction.ADDED.value, DiffAction.UPDATED.value}


def _query_changed(
    definition: ProposedChangeArtifactDefinition,
    diff_summary: list[NodeDiff],
) -> bool:
    """Return True when the definition's GraphQL query node is modified in the diff.

    The SDK inlines every fragment body into the stored query text before persisting,
    so any edit to the primary ``.gql`` file or any transitively referenced fragment
    surfaces as a single ``CoreGraphQLQuery`` node modification. A node-id match is
    therefore sufficient.

    Entries with ``action=unchanged`` are ignored because the diff system enriches
    the tree with parent context nodes that are not themselves modified, and entries
    with ``action=removed`` are ignored because a query deleted on the source branch
    leaves the definition broken and there is nothing to regenerate against.
    """
    return any(
        entry["id"] == definition.query_id and entry["action"] in _TRIGGERING_DIFF_ACTIONS for entry in diff_summary
    )


def _definition_changed(
    definition: ProposedChangeArtifactDefinition,
    diff_summary: list[NodeDiff],
) -> bool:
    """Return True when the ``CoreArtifactDefinition`` node itself is modified in the diff.

    Any attribute change or relationship repoint (``targets``, ``transformation``,
    ``query``) on the definition surfaces as a modification of the definition's own
    node id, so a single id-based check covers every shape of definition-level
    change uniformly.

    Entries with ``action=unchanged`` are ignored because the diff system enriches
    the tree with parent context nodes that are not themselves modified, and entries
    with ``action=removed`` cannot occur in practice here because the definition list
    is fetched from the source branch's current state.
    """
    return any(
        entry["id"] == definition.definition_id and entry["action"] in _TRIGGERING_DIFF_ACTIONS
        for entry in diff_summary
    )


def _transform_changed(
    definition: ProposedChangeArtifactDefinition,
    repo_diff: ProposedChangeRepository,
) -> bool:
    """Return True when the transform's stored dependency closure intersects this repo's file diff.

    Falls back to "any file changed in the repository" when the closure cannot
    be trusted. On the precise path, both sides are canonicalized before the
    set intersection so the comparison matches git's diff output regardless
    of input separator or leading prefix.
    """
    closure_trusted = definition.dependencies is not None and definition.dependencies_complete is True
    if not closure_trusted:
        return repo_diff.has_modifications

    if not definition.dependencies:
        return False

    closure = {canonicalize_path(entry) for entry in definition.dependencies}
    changed_files: set[str] = set()
    for raw in (*repo_diff.files_added, *repo_diff.files_changed, *repo_diff.files_removed):
        try:
            changed_files.add(canonicalize_path(raw))
        except ValueError:
            continue

    return bool(closure & changed_files)


def _repo_diff_or_none(branch_diff: ProposedChangeBranchDiff, repository_id: str) -> ProposedChangeRepository | None:
    try:
        return branch_diff.get_repository(repository_id)
    except NodeNotFoundError:
        return None


class DefinitionSelect(IntFlag):
    NONE = 0
    MODIFIED_KINDS = 1
    FILE_CHANGES = 2
    QUERY_CHANGED = 4
    DEFINITION_CHANGED = 8

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

        if DefinitionSelect.QUERY_CHANGED in self:
            change_types.append("changes to the GraphQL query")

        if DefinitionSelect.DEFINITION_CHANGED in self:
            change_types.append("changes to the artifact definition")

        if DefinitionSelect.FILE_CHANGES in self:
            change_types.append("file changes affecting the transform's dependencies")

        if self:
            return f"Requesting generation due to {' and '.join(change_types)}"

        return "Doesn't require changes due to no relevant modified kinds or file changes in Git"


@flow(name="proposed-changed-pipeline", flow_run_name="Execute proposed changed pipeline")
async def run_proposed_change_pipeline(model: RequestProposedChangePipeline, context: InfrahubContext) -> None:
    client = get_client()
    repositories = await _get_proposed_change_repositories(model=model, client=client)

    if model.source_branch_sync_with_git and await _validate_repository_merge_conflicts(
        repositories=repositories, client=client
    ):
        for repo in repositories:
            if not repo.read_only and repo.internal_status == RepositoryInternalStatus.ACTIVE.value:
                trigger_repo_checks_model = TriggerRepositoryInternalChecks(
                    proposed_change=model.proposed_change,
                    repository=repo.repository_id,
                    source_branch=repo.source_branch,
                    target_branch=repo.destination_branch,
                )
                await get_workflow().submit_workflow(
                    workflow=GIT_REPOSITORY_INTERNAL_CHECKS_TRIGGER,
                    context=context,
                    parameters={"model": trigger_repo_checks_model},
                )
        return

    await populate_repository_file_diffs(repositories=repositories, differ=GitRepositoryFileDiffer(client=client))

    database = await get_database()
    async with database.start_session() as dbs:
        destination_branch = await registry.get_branch(db=dbs, branch=model.destination_branch)
        source_branch = await registry.get_branch(db=dbs, branch=model.source_branch)
        component_registry = get_component_registry()
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=dbs, branch=source_branch)
        diff_coordinator.set_logger(get_run_logger())
        await diff_coordinator.update_branch_diff(
            base_branch=destination_branch, diff_branch=source_branch, proposed_change_id=model.proposed_change
        )

    client = get_client()

    diff_summary = await client.get_diff_summary(branch=model.source_branch)
    await set_diff_summary_cache(pipeline_id=model.pipeline_id, diff_summary=diff_summary, cache=await get_cache())
    branch_diff = ProposedChangeBranchDiff(pipeline_id=model.pipeline_id, repositories=repositories)
    branch_diff.subscribers.extend(
        await _get_subscribers_from_diff(diff_summary=diff_summary, branch=model.source_branch, client=client)
    )

    if model.check_type is CheckType.ARTIFACT:
        request_refresh_artifact_model = RequestProposedChangeRefreshArtifacts(
            proposed_change=model.proposed_change,
            source_branch=model.source_branch,
            source_branch_sync_with_git=model.source_branch_sync_with_git,
            destination_branch=model.destination_branch,
            branch_diff=branch_diff,
        )
        await get_workflow().submit_workflow(
            workflow=REQUEST_PROPOSED_CHANGE_REFRESH_ARTIFACTS,
            parameters={"model": request_refresh_artifact_model},
            context=context,
        )

    if model.check_type in [CheckType.ALL, CheckType.GENERATOR]:
        model_proposed_change_run_generator = RequestProposedChangeRunGenerators(
            proposed_change=model.proposed_change,
            source_branch=model.source_branch,
            source_branch_sync_with_git=model.source_branch_sync_with_git,
            destination_branch=model.destination_branch,
            branch_diff=branch_diff,
            refresh_artifacts=model.check_type is CheckType.ALL,
            do_repository_checks=model.check_type is CheckType.ALL,
        )
        await get_workflow().submit_workflow(
            workflow=REQUEST_PROPOSED_CHANGE_RUN_GENERATORS,
            context=context,
            parameters={"model": model_proposed_change_run_generator},
        )

    if model.check_type in [CheckType.ALL, CheckType.DATA] and has_node_changes(
        diff_summary=diff_summary, branch=model.source_branch
    ):
        model_proposed_change_data_integrity = RequestProposedChangeDataIntegrity(
            proposed_change=model.proposed_change,
            source_branch=model.source_branch,
            source_branch_sync_with_git=model.source_branch_sync_with_git,
            destination_branch=model.destination_branch,
            branch_diff=branch_diff,
        )
        await get_workflow().submit_workflow(
            workflow=REQUEST_PROPOSED_CHANGE_DATA_INTEGRITY,
            context=context,
            parameters={"model": model_proposed_change_data_integrity},
        )

    if model.check_type in [CheckType.REPOSITORY, CheckType.USER]:
        model_proposed_change_repo_checks = RequestProposedChangeRepositoryChecks(
            proposed_change=model.proposed_change,
            source_branch=model.source_branch,
            source_branch_sync_with_git=model.source_branch_sync_with_git,
            destination_branch=model.destination_branch,
            branch_diff=branch_diff,
        )
        await get_workflow().submit_workflow(
            workflow=REQUEST_PROPOSED_CHANGE_REPOSITORY_CHECKS,
            context=context,
            parameters={"model": model_proposed_change_repo_checks},
        )

    if model.check_type in [CheckType.ALL, CheckType.SCHEMA] and has_data_changes(
        diff_summary=diff_summary, branch=model.source_branch
    ):
        await get_workflow().submit_workflow(
            workflow=REQUEST_PROPOSED_CHANGE_SCHEMA_INTEGRITY,
            context=context,
            parameters={
                "model": RequestProposedChangeSchemaIntegrity(
                    proposed_change=model.proposed_change,
                    source_branch=model.source_branch,
                    source_branch_sync_with_git=model.source_branch_sync_with_git,
                    destination_branch=model.destination_branch,
                    branch_diff=branch_diff,
                )
            },
        )

    if model.check_type in [CheckType.ALL, CheckType.TEST]:
        await get_workflow().submit_workflow(
            workflow=REQUEST_PROPOSED_CHANGE_USER_TESTS,
            context=context,
            parameters={
                "model": RequestProposedChangeUserTests(
                    proposed_change=model.proposed_change,
                    source_branch=model.source_branch,
                    source_branch_sync_with_git=model.source_branch_sync_with_git,
                    destination_branch=model.destination_branch,
                    branch_diff=branch_diff,
                )
            },
        )


@flow(
    name="proposed-changed-refresh-artifacts",
    flow_run_name="Trigger artifacts refresh",
)
async def refresh_artifacts(model: RequestProposedChangeRefreshArtifacts, context: InfrahubContext) -> None:
    await add_tags(branches=[model.source_branch], nodes=[model.proposed_change])
    log = get_run_logger()

    client = get_client()

    definition_information = await client.execute_graphql(
        query=GATHER_ARTIFACT_DEFINITIONS,
        branch_name=model.source_branch,
    )
    artifact_definitions = _parse_artifact_definitions(
        definitions=definition_information[InfrahubKind.ARTIFACTDEFINITION]["edges"]
    )
    diff_summary = await get_diff_summary_cache(pipeline_id=model.branch_diff.pipeline_id)
    modified_kinds = get_modified_kinds(diff_summary=diff_summary, branch=model.source_branch)

    for artifact_definition in artifact_definitions:
        select = DefinitionSelect.NONE
        select = select.add_flag(
            current=select,
            flag=DefinitionSelect.QUERY_CHANGED,
            condition=_query_changed(definition=artifact_definition, diff_summary=diff_summary),
        )
        select = select.add_flag(
            current=select,
            flag=DefinitionSelect.DEFINITION_CHANGED,
            condition=_definition_changed(definition=artifact_definition, diff_summary=diff_summary),
        )
        repo_diff_for_definition = _repo_diff_or_none(
            branch_diff=model.branch_diff, repository_id=artifact_definition.repository_id
        )
        if repo_diff_for_definition is not None:
            select = select.add_flag(
                current=select,
                flag=DefinitionSelect.FILE_CHANGES,
                condition=_transform_changed(
                    definition=artifact_definition,
                    repo_diff=repo_diff_for_definition,
                ),
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
            request_artifacts_definitions_model = RequestArtifactDefinitionCheck(
                artifact_definition=artifact_definition,
                branch_diff=model.branch_diff,
                proposed_change=model.proposed_change,
                source_branch=model.source_branch,
                source_branch_sync_with_git=model.source_branch_sync_with_git,
                destination_branch=model.destination_branch,
            )

            await get_workflow().submit_workflow(
                REQUEST_ARTIFACT_DEFINITION_CHECK,
                parameters={"model": request_artifacts_definitions_model},
                context=context,
            )


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
            dependencies {
              value
            }
            dependencies_complete {
              value
            }
            query {
              node {
                id
                models {
                  value
                }
                name {
                  value
                }
                query {
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
    model: RequestProposedChangePipeline, source: list[dict], destination: list[dict]
) -> list[ProposedChangeRepository]:
    """This function assumes that the repos is a list of the edges.

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
                source_branch=model.source_branch,
                destination_branch=model.destination_branch,
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
                source_branch=model.source_branch,
                destination_branch=model.destination_branch,
            )
        else:
            pc_repos[repo.repository_id].source_commit = repo.commit
            pc_repos[repo.repository_id].internal_status = repo.internal_status

    return list(pc_repos.values())


def _parse_repositories(repositories: list[dict]) -> list[Repository]:
    """This function assumes that the repos is a list of the edges.

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
    """This function assumes that definitions is a list of the edges.

    The edge should be of type CoreArtifactDefinition from the query
    * GATHER_ARTIFACT_DEFINITIONS
    """
    parsed = []
    for definition in definitions:
        transformation = definition["node"]["transformation"]["node"]
        artifact_definition = ProposedChangeArtifactDefinition(
            definition_id=definition["node"]["id"],
            definition_name=definition["node"]["name"]["value"],
            artifact_name=definition["node"]["artifact_name"]["value"],
            content_type=definition["node"]["content_type"]["value"],
            timeout=transformation["timeout"]["value"],
            query_name=transformation["query"]["node"]["name"]["value"],
            query_id=transformation["query"]["node"]["id"],
            query_models=transformation["query"]["node"]["models"]["value"] or [],
            query_payload=transformation["query"]["node"]["query"]["value"],
            repository_id=transformation["repository"]["node"]["id"],
            transform_kind=transformation["__typename"],
            dependencies=transformation["dependencies"]["value"],
            dependencies_complete=transformation["dependencies_complete"]["value"],
        )
        if artifact_definition.transform_kind == InfrahubKind.TRANSFORMJINJA2:
            artifact_definition.template_path = transformation["template_path"]["value"]
        elif artifact_definition.transform_kind == InfrahubKind.TRANSFORMPYTHON:
            artifact_definition.class_name = transformation["class_name"]["value"]
            artifact_definition.file_path = transformation["file_path"]["value"]
            artifact_definition.convert_query_response = transformation["convert_query_response"]["value"]

        parsed.append(artifact_definition)

    return parsed


async def _get_proposed_change_repositories(
    model: RequestProposedChangePipeline, client: InfrahubClient
) -> list[ProposedChangeRepository]:
    destination_all = await client.execute_graphql(
        query=DESTINATION_ALLREPOSITORIES, branch_name=model.destination_branch
    )
    try:
        source_managed = await client.execute_graphql(query=SOURCE_REPOSITORIES, branch_name=model.source_branch)
        source_readonly = await client.execute_graphql(
            query=SOURCE_READONLY_REPOSITORIES, branch_name=model.source_branch
        )
    except URLNotFoundError:
        # If the URL is not found it means that the source branch has been deleted after the proposed change was created
        return []

    destination_all = destination_all[InfrahubKind.GENERICREPOSITORY]["edges"]
    source_all = (
        source_managed[InfrahubKind.REPOSITORY]["edges"] + source_readonly[InfrahubKind.READONLYREPOSITORY]["edges"]
    )

    return _parse_proposed_change_repositories(model=model, source=source_all, destination=destination_all)


@task(
    name="proposed-change-validate-repository-conflicts",
    task_run_name="Validate conflicts on repository",
    cache_policy=NONE,
)  # type: ignore[arg-type]
async def _validate_repository_merge_conflicts(
    repositories: list[ProposedChangeRepository], client: InfrahubClient
) -> bool:
    log = get_run_logger()

    conflicts = False
    for repo in repositories:
        if repo.has_diff and not repo.is_staging:
            git_repo = await InfrahubRepository.init(id=repo.repository_id, name=repo.repository_name, client=client)
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


async def _get_subscribers_for_nodes(
    node_ids: list[str], branch: str, client: InfrahubClient
) -> list[ProposedChangeSubscriber]:
    result = await client.execute_graphql(
        query=GATHER_GRAPHQL_QUERY_SUBSCRIBERS,
        branch_name=branch,
        variables={"members": node_ids},
    )
    subscribers = []
    for group in result[InfrahubKind.GRAPHQLQUERYGROUP]["edges"]:
        for subscriber in group["node"]["subscribers"]["edges"]:
            subscribers.append(
                ProposedChangeSubscriber(subscriber_id=subscriber["node"]["id"], kind=subscriber["node"]["__typename"])
            )
    return subscribers


async def _get_subscribers_from_diff(
    diff_summary: list[NodeDiff], branch: str, client: InfrahubClient
) -> list[ProposedChangeSubscriber]:
    return await _get_subscribers_for_nodes(
        node_ids=get_modified_node_ids(diff_summary=diff_summary, branch=branch),
        branch=branch,
        client=client,
    )
