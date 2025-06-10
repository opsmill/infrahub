from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.protocols import CoreArtifactValidator, CoreGeneratorDefinition, CoreProposedChange
from prefect import flow, task
from prefect.cache_policies import NONE
from prefect.client.schemas.objects import (
    State,  # noqa: TC002
)
from prefect.logging import get_run_logger
from prefect.states import Completed, Failed

from infrahub import config
from infrahub.artifacts.models import CheckArtifactCreate
from infrahub.context import InfrahubContext  # noqa: TC001  needed for prefect flow
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.branch.tasks import merge_branch
from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus, ValidatorConclusion
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.model.diff import DiffElementType, SchemaConflict
from infrahub.core.diff.model.path import NodeDiffFieldSummary
from infrahub.core.integrity.object_conflict.conflict_recorder import ObjectConflictValidatorRecorder
from infrahub.core.protocols import CoreDataCheck, CoreValidator
from infrahub.core.protocols import CoreProposedChange as InternalCoreProposedChange
from infrahub.core.validators.checks_runner import run_checks_and_update_validator
from infrahub.core.validators.determiner import ConstraintValidatorDeterminer
from infrahub.core.validators.models.validate_migration import SchemaValidateMigrationData
from infrahub.core.validators.tasks import schema_validate_migrations
from infrahub.dependencies.registry import get_component_registry
from infrahub.exceptions import MergeFailedError
from infrahub.generators.models import ProposedChangeGeneratorDefinition
from infrahub.git.models import TriggerRepositoryInternalChecks, TriggerRepositoryUserChecks
from infrahub.git.repository import get_initialized_repo
from infrahub.log import get_logger
from infrahub.message_bus import InfrahubMessage, messages
from infrahub.message_bus.operations.requests.proposed_change import DefinitionSelect
from infrahub.proposed_change.constants import ProposedChangeState
from infrahub.proposed_change.models import (
    RequestArtifactDefinitionCheck,
    RequestProposedChangeDataIntegrity,
    RequestProposedChangeRepositoryChecks,
    RequestProposedChangeRunGenerators,
    RequestProposedChangeSchemaIntegrity,
    RequestProposedChangeUserTests,
)
from infrahub.pytest_plugin import InfrahubBackendPlugin
from infrahub.services import InfrahubServices  # noqa: TC001  needed for prefect flow
from infrahub.validators.tasks import start_validator
from infrahub.workflows.catalogue import (
    GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE,
    GIT_REPOSITORY_INTERNAL_CHECKS_TRIGGER,
    GIT_REPOSITORY_USER_CHECKS_TRIGGER,
    REQUEST_PROPOSED_CHANGE_REPOSITORY_CHECKS,
)
from infrahub.workflows.utils import add_tags

from .branch_diff import get_diff_summary_cache, get_modified_kinds

if TYPE_CHECKING:
    from infrahub_sdk.diff import NodeDiff
    from infrahub_sdk.node import InfrahubNode

    from infrahub.core.models import SchemaUpdateConstraintInfo
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.message_bus.types import ProposedChangeRepository


async def _proposed_change_transition_state(
    state: ProposedChangeState,
    service: InfrahubServices,
    proposed_change: InternalCoreProposedChange | None = None,
    proposed_change_id: str | None = None,
) -> None:
    async with service.database.start_session() as db:
        if proposed_change is None and proposed_change_id:
            proposed_change = await registry.manager.get_one(
                db=db, id=proposed_change_id, kind=InternalCoreProposedChange, raise_on_error=True
            )
        if proposed_change:
            proposed_change.state.value = state.value  # type: ignore[misc]
            await proposed_change.save(db=db)


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
    service: InfrahubServices,
) -> State:
    log = get_run_logger()

    await add_tags(nodes=[proposed_change_id])

    async with service.database.start_session() as db:
        proposed_change = await registry.manager.get_one(
            db=db, id=proposed_change_id, kind=InternalCoreProposedChange, raise_on_error=True
        )

        log.info("Validating if all conditions are met to merge the proposed change")

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
                    proposed_change=proposed_change, state=ProposedChangeState.OPEN, service=service
                )
                return Failed(message="Unable to merge proposed change containing failing checks")
            if validator_kind == InfrahubKind.DATAVALIDATOR:
                data_checks = await validation.checks.get_peers(db=db, peer_type=CoreDataCheck)
                for check in data_checks.values():
                    if check.conflicts.value and not check.keep_branch.value:
                        await _proposed_change_transition_state(
                            proposed_change=proposed_change, state=ProposedChangeState.OPEN, service=service
                        )
                        return Failed(
                            message="Data conflicts found on branch and missing decisions about what branch to keep"
                        )

        log.info("Proposed change is eligible to be merged")
        try:
            await merge_branch(
                branch=source_branch.name, context=context, service=service, proposed_change_id=proposed_change_id
            )
        except MergeFailedError as exc:
            await _proposed_change_transition_state(
                proposed_change=proposed_change, state=ProposedChangeState.OPEN, service=service
            )
            return Failed(message=f"Merge failure when trying to merge {exc.message}")

        log.info(f"Branch {source_branch.name} has been merged successfully")

        await _proposed_change_transition_state(
            proposed_change=proposed_change, state=ProposedChangeState.MERGED, service=service
        )
        return Completed(message="proposed change merged successfully")


@flow(
    name="proposed-changes-cancel-branch",
    flow_run_name="Cancel all proposed change associated with branch {branch_name}",
    description="Cancel all Proposed change associated with a branch.",
)
async def cancel_proposed_changes_branch(branch_name: str, service: InfrahubServices) -> None:
    await add_tags(branches=[branch_name])

    proposed_changed_opened = await service.client.filters(
        kind=CoreProposedChange,
        include=["id", "source_branch"],
        state__value=ProposedChangeState.OPEN.value,
        source_branch__value=branch_name,
    )
    proposed_changed_closed = await service.client.filters(
        kind=CoreProposedChange,
        include=["id", "source_branch"],
        state__value=ProposedChangeState.CLOSED.value,
        source_branch__value=branch_name,
    )

    for proposed_change in proposed_changed_opened + proposed_changed_closed:
        await cancel_proposed_change(proposed_change=proposed_change, service=service)


@task(name="Cancel a propose change", description="Cancel a propose change", cache_policy=NONE)  # type: ignore[arg-type]
async def cancel_proposed_change(proposed_change: CoreProposedChange, service: InfrahubServices) -> None:
    await add_tags(nodes=[proposed_change.id])
    log = get_run_logger()

    log.info("Canceling proposed change as the source branch was deleted")
    proposed_change = await service.client.get(kind=CoreProposedChange, id=proposed_change.id)
    proposed_change.state.value = ProposedChangeState.CANCELED.value
    await proposed_change.save()


@flow(
    name="proposed-changed-data-integrity",
    flow_run_name="Triggers data integrity check",
)
async def run_proposed_change_data_integrity_check(
    model: RequestProposedChangeDataIntegrity, service: InfrahubServices
) -> None:
    """Triggers a data integrity validation check on the provided proposed change to start."""
    await add_tags(branches=[model.source_branch], nodes=[model.proposed_change])

    async with service.database.start_transaction() as dbt:
        destination_branch = await registry.get_branch(db=dbt, branch=model.destination_branch)
        source_branch = await registry.get_branch(db=dbt, branch=model.source_branch)
        component_registry = get_component_registry()

        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=dbt, branch=source_branch)
        await diff_coordinator.update_branch_diff(base_branch=destination_branch, diff_branch=source_branch)


@flow(
    name="proposed-changed-run-generator",
    flow_run_name="Run generators",
)
async def run_generators(
    model: RequestProposedChangeRunGenerators, context: InfrahubContext, service: InfrahubServices
) -> None:
    await add_tags(branches=[model.source_branch], nodes=[model.proposed_change], db_change=True)

    generators = await service.client.filters(
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
        )
        for generator in generators
    ]

    diff_summary = await get_diff_summary_cache(pipeline_id=model.branch_diff.pipeline_id, cache=service.cache)
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
            msg = messages.RequestGeneratorDefinitionCheck(
                context=context,
                generator_definition=generator_definition,
                branch_diff=model.branch_diff,
                proposed_change=model.proposed_change,
                source_branch=model.source_branch,
                source_branch_sync_with_git=model.source_branch_sync_with_git,
                destination_branch=model.destination_branch,
            )
            msg.assign_meta(parent=model)
            await service.message_bus.send(message=msg)

    next_messages: list[InfrahubMessage] = []
    if model.refresh_artifacts:
        next_messages.append(
            messages.RequestProposedChangeRefreshArtifacts(
                context=context,
                proposed_change=model.proposed_change,
                source_branch=model.source_branch,
                source_branch_sync_with_git=model.source_branch_sync_with_git,
                destination_branch=model.destination_branch,
                branch_diff=model.branch_diff,
            )
        )

    if model.do_repository_checks:
        model_proposed_change_repo_checks = RequestProposedChangeRepositoryChecks(
            proposed_change=model.proposed_change,
            source_branch=model.source_branch,
            source_branch_sync_with_git=model.source_branch_sync_with_git,
            destination_branch=model.destination_branch,
            branch_diff=model.branch_diff,
        )
        await service.workflow.submit_workflow(
            workflow=REQUEST_PROPOSED_CHANGE_REPOSITORY_CHECKS,
            context=context,
            parameters={"model": model_proposed_change_repo_checks},
        )

    for next_msg in next_messages:
        next_msg.assign_meta(parent=model)
        await service.message_bus.send(message=next_msg)


@flow(
    name="proposed-changed-schema-integrity",
    flow_run_name="Process schema integrity",
)
async def run_proposed_change_schema_integrity_check(
    model: RequestProposedChangeSchemaIntegrity, service: InfrahubServices
) -> None:
    # For now, we retrieve the latest schema for each branch from the registry
    # In the future it would be good to generate the object SchemaUpdateValidationResult from message.branch_diff
    await add_tags(branches=[model.source_branch], nodes=[model.proposed_change])

    source_schema = registry.schema.get_schema_branch(name=model.source_branch).duplicate()
    dest_schema = registry.schema.get_schema_branch(name=model.destination_branch).duplicate()

    candidate_schema = dest_schema.duplicate()
    candidate_schema.update(schema=source_schema)
    schema_diff = dest_schema.diff(other=candidate_schema)
    validation_result = dest_schema.validate_update(other=candidate_schema, diff=schema_diff)

    diff_summary = await get_diff_summary_cache(pipeline_id=model.branch_diff.pipeline_id, cache=service.cache)
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
        ),
        service=service,
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
            elif element_type.lower() in (DiffElementType.ATTRIBUTE.value.lower(),):
                field_summary.attribute_names.add(element_name)

    determiner = ConstraintValidatorDeterminer(schema_branch=schema)
    return await determiner.get_constraints(node_diffs=list(node_diff_field_summary_map.values()))


@flow(
    name="proposed-changed-repository-checks",
    flow_run_name="Process user defined checks",
)
async def repository_checks(
    model: RequestProposedChangeRepositoryChecks, service: InfrahubServices, context: InfrahubContext
) -> None:
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
            await service.workflow.submit_workflow(
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
        await service.workflow.submit_workflow(
            workflow=GIT_REPOSITORY_USER_CHECKS_TRIGGER,
            context=context,
            parameters={"model": trigger_user_checks_model},
        )


@flow(
    name="proposed-changed-user-tests",
    flow_run_name="Run unit tests in repositories",
)
async def run_proposed_change_user_tests(model: RequestProposedChangeUserTests, service: InfrahubServices) -> None:
    log = get_run_logger()
    await add_tags(branches=[model.source_branch], nodes=[model.proposed_change])
    proposed_change = await service.client.get(kind=InfrahubKind.PROPOSEDCHANGE, id=model.proposed_change)

    def _execute(
        directory: Path, repository: ProposedChangeRepository, proposed_change: InfrahubNode
    ) -> int | pytest.ExitCode:
        config_file = str(directory / ".infrahub.yml")
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
                plugins=[InfrahubBackendPlugin(service.client.config, repository.repository_id, proposed_change.id)],
            )

        # Restore stdout/stderr back to their orignal states
        sys.stdout = old_out
        sys.stderr = old_err

        return exit_code

    for repository in model.branch_diff.repositories:
        if model.source_branch_sync_with_git:
            repo = await get_initialized_repo(
                repository_id=repository.repository_id,
                name=repository.repository_name,
                service=service,
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
async def validate_artifacts_generation(model: RequestArtifactDefinitionCheck, service: InfrahubServices) -> None:
    await add_tags(branches=[model.source_branch], nodes=[model.proposed_change], db_change=True)

    log = get_run_logger()
    artifact_definition = await service.client.get(
        kind=InfrahubKind.ARTIFACTDEFINITION,
        id=model.artifact_definition.definition_id,
        branch=model.source_branch,
    )
    proposed_change = await service.client.get(kind=InfrahubKind.PROPOSEDCHANGE, id=model.proposed_change)

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
        service=service,
        validator=previous_validator,
        validator_type=CoreArtifactValidator,
        proposed_change=model.proposed_change,
        data={
            "label": validator_name,
            "definition": model.artifact_definition.definition_id,
        },
        context=model.context,
    )

    await artifact_definition.targets.fetch()
    group = artifact_definition.targets.peer
    await group.members.fetch()

    existing_artifacts = await service.client.filters(
        kind=InfrahubKind.ARTIFACT,
        definition__ids=[model.artifact_definition.definition_id],
        include=["object"],
        branch=model.source_branch,
    )
    artifacts_by_member = {}
    for artifact in existing_artifacts:
        artifacts_by_member[artifact.object.peer.id] = artifact.id

    repository = model.branch_diff.get_repository(repository_id=model.artifact_definition.repository_id)
    impacted_artifacts = model.branch_diff.get_subscribers_ids(kind=InfrahubKind.ARTIFACT)

    checks = []

    for relationship in group.members.peers:
        member = relationship.peer
        artifact_id = artifacts_by_member.get(member.id)
        if _should_render_artifact(
            artifact_id=artifact_id,
            managed_branch=model.source_branch_sync_with_git,
            impacted_artifacts=impacted_artifacts,
        ):
            log.info(f"Trigger Artifact processing for {member.display_label}")

            check_model = CheckArtifactCreate(
                context=model.context,
                artifact_name=model.artifact_definition.artifact_name,
                artifact_id=artifact_id,
                artifact_definition=model.artifact_definition.definition_id,
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
                variables=member.extract(params=artifact_definition.parameters.value),
                target_id=member.id,
                target_kind=member.get_kind(),
                target_name=member.display_label,
                timeout=model.artifact_definition.timeout,
                validator_id=validator.id,
            )

            checks.append(
                service.workflow.execute_workflow(
                    workflow=GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE,
                    parameters={"model": check_model},
                    expected_return=ValidatorConclusion,
                )
            )

    await run_checks_and_update_validator(
        checks=checks,
        validator=validator,
        proposed_change_id=model.proposed_change,
        context=model.context,
        service=service,
    )


def _should_render_artifact(artifact_id: str | None, managed_branch: bool, impacted_artifacts: list[str]) -> bool:  # noqa: ARG001
    """Returns a boolean to indicate if an artifact should be generated or not.
    Will return true if:
        * The artifact_id wasn't set which could be that it's a new object that doesn't have a previous artifact
        * The source brance is not data only which would indicate that it could contain updates in git to the transform
        * The artifact_id exists in the impacted_artifacts list
    Will return false if:
        * The source branch is a data only branch and the artifact_id exists and is not in the impacted list
    """

    # if not artifact_id or managed_branch:
    #    return True
    # return artifact_id in impacted_artifacts
    # Temporary workaround tracked in https://github.com/opsmill/infrahub/issues/4991
    return True
