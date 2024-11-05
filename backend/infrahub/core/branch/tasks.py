from __future__ import annotations

from prefect import flow, get_run_logger

from infrahub import lock
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.ipam_diff_parser import IpamDiffParser
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.merge import BranchMerger
from infrahub.core.migrations.schema.models import SchemaApplyMigrationData
from infrahub.core.migrations.schema.tasks import schema_apply_migrations
from infrahub.core.validators.determiner import ConstraintValidatorDeterminer
from infrahub.core.validators.models.validate_migration import SchemaValidateMigrationData
from infrahub.core.validators.tasks import schema_validate_migrations
from infrahub.dependencies.registry import get_component_registry
from infrahub.events.branch_action import BranchDeleteEvent
from infrahub.exceptions import MergeFailedError, ValidationError
from infrahub.log import get_log_data
from infrahub.message_bus import Meta, messages
from infrahub.services import services
from infrahub.worker import WORKER_IDENTITY
from infrahub.workflows.catalogue import BRANCH_CANCEL_PROPOSED_CHANGES, IPAM_RECONCILIATION
from infrahub.workflows.utils import add_branch_tag


@flow(name="branch-rebase")
async def rebase_branch(branch: str) -> None:
    service = services.service
    log = get_run_logger()
    await add_branch_tag(branch_name=branch)

    obj = await Branch.get_by_name(db=service.database, name=branch)
    base_branch = await Branch.get_by_name(db=service.database, name=registry.default_branch)
    component_registry = get_component_registry()
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=service.database, branch=obj)
    diff_merger = await component_registry.get_component(DiffMerger, db=service.database, branch=obj)
    merger = BranchMerger(
        db=service.database,
        diff_coordinator=diff_coordinator,
        diff_merger=diff_merger,
        source_branch=obj,
        service=service,
    )
    diff_repository = await component_registry.get_component(DiffRepository, db=service.database, branch=obj)
    enriched_diff = await diff_coordinator.update_branch_diff(base_branch=base_branch, diff_branch=obj)
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
        error_messages = await schema_validate_migrations(
            message=SchemaValidateMigrationData(branch=obj, schema_branch=candidate_schema, constraints=constraints)
        )
        if error_messages:
            raise ValidationError(",\n".join(error_messages))

    schema_in_main_before = merger.destination_schema.duplicate()

    async with lock.registry.global_graph_lock():
        async with service.database.start_transaction() as dbt:
            await obj.rebase(db=dbt)
            log.info("Branch successfully rebased")

        if obj.has_schema_changes:
            # NOTE there is a bit additional work in order to calculate a proper diff that will
            # allow us to pull only the part of the schema that has changed, for now the safest option is to pull
            # Everything
            # schema_diff = await merger.has_schema_changes()
            # TODO Would be good to convert this part to a Prefect Task in order to track it properly
            updated_schema = await registry.schema.load_schema_from_db(
                db=service.database,
                branch=obj,
                # schema=merger.source_schema.duplicate(),
                # schema_diff=schema_diff,
            )
            registry.schema.set_schema_branch(name=obj.name, schema=updated_schema)
            obj.update_schema_hash()
            await obj.save(db=service.database)

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
    differ = await merger.get_graph_diff()
    diff_parser = IpamDiffParser(
        db=service.database,
        differ=differ,
        source_branch_name=obj.name,
        target_branch_name=registry.default_branch,
    )
    ipam_node_details = await diff_parser.get_changed_ipam_node_details()
    await service.workflow.submit_workflow(
        workflow=IPAM_RECONCILIATION, parameters={"branch": obj.name, "ipam_node_details": ipam_node_details}
    )

    # -------------------------------------------------------------
    # Generate an event to indicate that a branch has been rebased
    # NOTE: we still need to convert this event and potentially pull
    #   some tasks currently executed based on the event into this workflow
    # -------------------------------------------------------------
    log_data = get_log_data()
    request_id = log_data.get("request_id", "")
    message = messages.EventBranchRebased(
        branch=obj.name,
        meta=Meta(initiator_id=WORKER_IDENTITY, request_id=request_id),
    )
    await service.send(message=message)


@flow(name="branch-merge")
async def merge_branch(branch: str) -> None:
    service = services.service
    log = get_run_logger()

    await add_branch_tag(branch_name=branch)
    await add_branch_tag(branch_name=registry.default_branch)

    obj = await Branch.get_by_name(db=service.database, name=branch)
    component_registry = get_component_registry()

    merger: BranchMerger | None = None
    async with lock.registry.global_graph_lock():
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=service.database, branch=obj)
        diff_merger = await component_registry.get_component(DiffMerger, db=service.database, branch=obj)
        merger = BranchMerger(
            db=service.database,
            diff_coordinator=diff_coordinator,
            diff_merger=diff_merger,
            source_branch=obj,
            service=service,
        )
        try:
            await merger.merge()
        except Exception as exc:
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
    differ = await merger.get_graph_diff()
    diff_parser = IpamDiffParser(
        db=service.database,
        differ=differ,
        source_branch_name=obj.name,
        target_branch_name=registry.default_branch,
    )
    ipam_node_details = await diff_parser.get_changed_ipam_node_details()
    await service.workflow.submit_workflow(
        workflow=IPAM_RECONCILIATION,
        parameters={"branch": registry.default_branch, "ipam_node_details": ipam_node_details},
    )

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


@flow(name="branch-delete")
async def delete_branch(branch: str) -> None:
    service = services.service

    await add_branch_tag(branch_name=branch)

    obj = await Branch.get_by_name(db=service.database, name=str(branch))
    event = BranchDeleteEvent(branch=branch, branch_id=obj.get_id(), sync_with_git=obj.sync_with_git)
    await obj.delete(db=service.database)

    await service.workflow.submit_workflow(workflow=BRANCH_CANCEL_PROPOSED_CHANGES, parameters={"branch_name": branch})

    await service.event.send(event=event)
