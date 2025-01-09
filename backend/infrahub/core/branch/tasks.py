from __future__ import annotations

from datetime import timedelta
from typing import Any

import pydantic
from prefect import flow, get_run_logger
from prefect.automations import AutomationCore
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import DeploymentFilter, DeploymentFilterName
from prefect.client.schemas.objects import State  # noqa: TC002
from prefect.events.actions import RunDeployment
from prefect.events.schemas.automations import EventTrigger, Posture
from prefect.states import Completed, Failed

from infrahub import lock
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.ipam_diff_parser import IpamDiffParser
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.model.path import BranchTrackingId
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.merge import BranchMerger
from infrahub.core.migrations.schema.models import SchemaApplyMigrationData
from infrahub.core.migrations.schema.tasks import schema_apply_migrations
from infrahub.core.validators.determiner import ConstraintValidatorDeterminer
from infrahub.core.validators.models.validate_migration import SchemaValidateMigrationData
from infrahub.core.validators.tasks import schema_validate_migrations
from infrahub.dependencies.registry import get_component_registry
from infrahub.events.branch_action import BranchCreateEvent, BranchDeleteEvent, BranchRebaseEvent
from infrahub.exceptions import BranchNotFoundError, MergeFailedError, ValidationError
from infrahub.graphql.mutations.models import BranchCreateModel  # noqa: TC001
from infrahub.log import get_log_data
from infrahub.message_bus import Meta, messages
from infrahub.services import services
from infrahub.worker import WORKER_IDENTITY
from infrahub.workflows.catalogue import (
    BRANCH_CANCEL_PROPOSED_CHANGES,
    COMPUTED_ATTRIBUTE_REMOVE_PYTHON,
    COMPUTED_ATTRIBUTE_SETUP_PYTHON,
    DIFF_REFRESH_ALL,
    GIT_REPOSITORIES_CREATE_BRANCH,
    IPAM_RECONCILIATION,
)
from infrahub.workflows.utils import add_branch_tag

from .constants import AUTOMATION_NAME_CREATE, AUTOMATION_NAME_REMOVE


@flow(name="branch-rebase", flow_run_name="Rebase branch {branch}")
async def rebase_branch(branch: str) -> None:
    service = services.service

    async with service.database.start_session() as db:
        log = get_run_logger()
        await add_branch_tag(branch_name=branch)
        obj = await Branch.get_by_name(db=db, name=branch)
        base_branch = await Branch.get_by_name(db=db, name=registry.default_branch)
        component_registry = get_component_registry()
        diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=obj)
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=obj)
        diff_merger = await component_registry.get_component(DiffMerger, db=db, branch=obj)
        merger = BranchMerger(
            db=db,
            diff_coordinator=diff_coordinator,
            diff_merger=diff_merger,
            diff_repository=diff_repository,
            source_branch=obj,
            service=service,
        )
        diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=obj)
        enriched_diff = await diff_coordinator.update_branch_diff_and_return(base_branch=base_branch, diff_branch=obj)
        if enriched_diff.get_all_conflicts():
            raise ValidationError(
                f"Branch {obj.name} contains conflicts with the default branch that must be addressed."
                " Please review the diff for details and manually update the conflicts before rebasing."
            )
        node_diff_field_summaries = await diff_repository.get_node_field_summaries(
            diff_branch_name=enriched_diff.diff_branch_name, diff_id=enriched_diff.uuid
        )

        candidate_schema = merger.get_candidate_schema()
        determiner = ConstraintValidatorDeterminer(schema_branch=candidate_schema)
        constraints = await determiner.get_constraints(node_diffs=node_diff_field_summaries)

        # If there are some changes related to the schema between this branch and main, we need to
        #  - Run all the validations to ensure everything is correct before rebasing the branch
        #  - Run all the migrations after the rebase
        if obj.has_schema_changes:
            constraints += await merger.calculate_validations(target_schema=candidate_schema)
        if constraints:
            responses = await schema_validate_migrations(
                message=SchemaValidateMigrationData(branch=obj, schema_branch=candidate_schema, constraints=constraints)
            )
            error_messages = [violation.message for response in responses for violation in response.violations]
            if error_messages:
                raise ValidationError(",\n".join(error_messages))

        schema_in_main_before = merger.destination_schema.duplicate()

        async with lock.registry.global_graph_lock():
            async with db.start_transaction() as dbt:
                await obj.rebase(db=dbt)
                log.info("Branch successfully rebased")

            if obj.has_schema_changes:
                # NOTE there is a bit additional work in order to calculate a proper diff that will
                # allow us to pull only the part of the schema that has changed, for now the safest option is to pull
                # Everything
                # schema_diff = await merger.has_schema_changes()
                # TODO Would be good to convert this part to a Prefect Task in order to track it properly
                updated_schema = await registry.schema.load_schema_from_db(
                    db=db,
                    branch=obj,
                    # schema=merger.source_schema.duplicate(),
                    # schema_diff=schema_diff,
                )
                registry.schema.set_schema_branch(name=obj.name, schema=updated_schema)
                obj.update_schema_hash()
                await obj.save(db=db)

                # Execute the migrations
                migrations = await merger.calculate_migrations(target_schema=updated_schema)

                errors = await schema_apply_migrations(
                    message=SchemaApplyMigrationData(
                        branch=merger.source_branch,
                        new_schema=candidate_schema,
                        previous_schema=schema_in_main_before,
                        migrations=migrations,
                    )
                )
                for error in errors:
                    log.error(error)

        # -------------------------------------------------------------
        # Trigger the reconciliation of IPAM data after the rebase
        # -------------------------------------------------------------
        diff_parser = await component_registry.get_component(IpamDiffParser, db=db, branch=obj)
        ipam_node_details = await diff_parser.get_changed_ipam_node_details(
            source_branch_name=obj.name,
            target_branch_name=registry.default_branch,
        )
        if ipam_node_details:
            await service.workflow.submit_workflow(
                workflow=IPAM_RECONCILIATION, parameters={"branch": obj.name, "ipam_node_details": ipam_node_details}
            )

    await service.workflow.submit_workflow(workflow=DIFF_REFRESH_ALL, parameters={"branch_name": obj.name})

    # -------------------------------------------------------------
    # Generate an event to indicate that a branch has been rebased
    # -------------------------------------------------------------
    await service.event.send(event=BranchRebaseEvent(branch=obj.name, branch_id=obj.get_id()))


@flow(name="branch-merge", flow_run_name="Merge branch {branch} into main")
async def merge_branch(branch: str) -> None:
    service = services.service
    async with service.database.start_session() as db:
        log = get_run_logger()

        await add_branch_tag(branch_name=branch)
        await add_branch_tag(branch_name=registry.default_branch)

        obj = await Branch.get_by_name(db=db, name=branch)
        component_registry = get_component_registry()

        merger: BranchMerger | None = None
        async with lock.registry.global_graph_lock():
            # await update_diff(model=RequestDiffUpdate(branch_name=obj.name))

            diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=obj)
            diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=obj)
            diff_merger = await component_registry.get_component(DiffMerger, db=db, branch=obj)
            merger = BranchMerger(
                db=db,
                diff_coordinator=diff_coordinator,
                diff_merger=diff_merger,
                diff_repository=diff_repository,
                source_branch=obj,
                service=service,
            )
            try:
                await merger.merge()
            except Exception as exc:
                log.exception("Merge failed, beginning rollback")
                await merger.rollback()
                raise MergeFailedError(branch_name=branch) from exc
            await merger.update_schema()

        if merger and merger.migrations:
            errors = await schema_apply_migrations(
                message=SchemaApplyMigrationData(
                    branch=merger.destination_branch,
                    new_schema=merger.destination_schema,
                    previous_schema=merger.initial_source_schema,
                    migrations=merger.migrations,
                )
            )
            for error in errors:
                log.error(error)

        # -------------------------------------------------------------
        # Trigger the reconciliation of IPAM data after the merge
        # -------------------------------------------------------------
        diff_parser = await component_registry.get_component(IpamDiffParser, db=db, branch=obj)
        ipam_node_details = await diff_parser.get_changed_ipam_node_details(
            source_branch_name=obj.name,
            target_branch_name=registry.default_branch,
        )
        if ipam_node_details:
            await service.workflow.submit_workflow(
                workflow=IPAM_RECONCILIATION,
                parameters={"branch": registry.default_branch, "ipam_node_details": ipam_node_details},
            )
        # -------------------------------------------------------------
        # remove tracking ID from the diff because there is no diff after the merge
        # -------------------------------------------------------------
        diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=obj)
        await diff_repository.drop_tracking_ids(tracking_ids=[BranchTrackingId(name=obj.name)])

        # -------------------------------------------------------------
        # Generate an event to indicate that a branch has been merged
        # NOTE: we still need to convert this event and potentially pull
        #   some tasks currently executed based on the event into this workflow
        # -------------------------------------------------------------
        log_data = get_log_data()
        request_id = log_data.get("request_id", "")
        message = messages.EventBranchMerge(
            source_branch=obj.name,
            target_branch=registry.default_branch,
            meta=Meta(initiator_id=WORKER_IDENTITY, request_id=request_id),
        )
        await service.send(message=message)


@flow(name="branch-delete", flow_run_name="Delete branch {branch}")
async def delete_branch(branch: str) -> None:
    service = services.service

    await add_branch_tag(branch_name=branch)

    async with service.database.start_session() as db:
        obj = await Branch.get_by_name(db=db, name=str(branch))
        event = BranchDeleteEvent(branch=branch, branch_id=obj.get_id(), sync_with_git=obj.sync_with_git)
        await obj.delete(db=db)

        await service.workflow.submit_workflow(
            workflow=BRANCH_CANCEL_PROPOSED_CHANGES, parameters={"branch_name": branch}
        )

        await service.event.send(event=event)


@flow(
    name="branch-validate",
    flow_run_name="Validate branch {branch} for conflicts",
    description="Validate if the branch has some conflicts",
    persist_result=True,
)
async def validate_branch(branch: str) -> State:
    service = services.service
    await add_branch_tag(branch_name=branch)

    async with service.database.start_session() as db:
        obj = await Branch.get_by_name(db=db, name=branch)

        component_registry = get_component_registry()
        diff_repo = await component_registry.get_component(DiffRepository, db=db, branch=obj)
        has_conflicts = await diff_repo.diff_has_conflicts(
            diff_branch_name=obj.name, tracking_id=BranchTrackingId(name=obj.name)
        )
        if has_conflicts:
            return Failed(message="branch has some conflicts")
        return Completed(message="branch is valid")


@flow(name="create-branch", flow_run_name="Create branch {model.name}")
async def create_branch(model: BranchCreateModel) -> None:
    service = services.service
    await add_branch_tag(model.name)

    async with service.database.start_session() as db:
        try:
            await Branch.get_by_name(db=db, name=model.name)
            raise ValueError(f"The branch {model.name}, already exist")
        except BranchNotFoundError:
            pass

        data_dict: dict[str, Any] = dict(model)
        if "is_isolated" in data_dict:
            del data_dict["is_isolated"]

        try:
            obj = Branch(**data_dict)
        except pydantic.ValidationError as exc:
            error_msgs = [f"invalid field {error['loc'][0]}: {error['msg']}" for error in exc.errors()]
            raise ValueError("\n".join(error_msgs)) from exc

        async with lock.registry.local_schema_lock():
            # Copy the schema from the origin branch and set the hash and the schema_changed_at value
            origin_schema = registry.schema.get_schema_branch(name=obj.origin_branch)
            new_schema = origin_schema.duplicate(name=obj.name)
            registry.schema.set_schema_branch(name=obj.name, schema=new_schema)
            obj.update_schema_hash()
            await obj.save(db=db)

            # Add Branch to registry
            registry.branch[obj.name] = obj
            await service.component.refresh_schema_hash(branches=[obj.name])

        event = BranchCreateEvent(branch=obj.name, branch_id=str(obj.uuid), sync_with_git=obj.sync_with_git)
        await service.event.send(event=event)

        if obj.sync_with_git:
            await service.workflow.submit_workflow(
                workflow=GIT_REPOSITORIES_CREATE_BRANCH,
                parameters={"branch": obj.name, "branch_id": str(obj.uuid)},
            )


@flow(name="branch-actions-setup", flow_run_name="Setup branch action events in task-manager")
async def branch_actions_setup() -> None:
    log = get_run_logger()

    async with get_client(sync_client=False) as client:
        deployments = {
            item.name: item
            for item in await client.read_deployments(
                deployment_filter=DeploymentFilter(
                    name=DeploymentFilterName(
                        any_=[COMPUTED_ATTRIBUTE_SETUP_PYTHON.name, COMPUTED_ATTRIBUTE_REMOVE_PYTHON.name]
                    )
                )
            )
        }
        deployment_id_computed_attribute_setup_python = deployments[COMPUTED_ATTRIBUTE_SETUP_PYTHON.name].id
        deployment_id_computed_attribute_remove_python = deployments[COMPUTED_ATTRIBUTE_REMOVE_PYTHON.name].id

        branch_create_automation = await client.find_automation(id_or_name=AUTOMATION_NAME_CREATE)

        automation = AutomationCore(
            name=AUTOMATION_NAME_CREATE,
            description="Trigger actions on branch create event",
            enabled=True,
            trigger=EventTrigger(
                posture=Posture.Reactive,
                expect={"infrahub.branch.created"},
                within=timedelta(0),
                threshold=1,
            ),
            actions=[
                RunDeployment(
                    source="selected",
                    deployment_id=deployment_id_computed_attribute_setup_python,
                    parameters={
                        "branch_name": "{{ event.resource['infrahub.branch.name'] }}",
                        "trigger_updates": False,
                    },
                    job_variables={},
                ),
            ],
        )

        if branch_create_automation:
            await client.update_automation(automation_id=branch_create_automation.id, automation=automation)
            log.info(f"{AUTOMATION_NAME_CREATE} Updated")
        else:
            await client.create_automation(automation=automation)
            log.info(f"{AUTOMATION_NAME_CREATE} Created")

        branch_remove_automation = await client.find_automation(id_or_name=AUTOMATION_NAME_REMOVE)

        automation = AutomationCore(
            name=AUTOMATION_NAME_REMOVE,
            description="Trigger actions on branch delete event",
            enabled=True,
            trigger=EventTrigger(
                posture=Posture.Reactive,
                expect={"infrahub.branch.deleted"},
                within=timedelta(0),
                threshold=1,
            ),
            actions=[
                RunDeployment(
                    source="selected",
                    deployment_id=deployment_id_computed_attribute_remove_python,
                    parameters={
                        "branch_name": "{{ event.resource['infrahub.branch.name'] }}",
                    },
                    job_variables={},
                ),
            ],
        )

        if branch_remove_automation:
            await client.update_automation(automation_id=branch_remove_automation.id, automation=automation)
            log.info(f"{AUTOMATION_NAME_REMOVE} Updated")
        else:
            await client.create_automation(automation=automation)
            log.info(f"{AUTOMATION_NAME_REMOVE} Created")
