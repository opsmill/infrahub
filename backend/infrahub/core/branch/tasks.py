from __future__ import annotations

from typing import Any
from uuid import uuid4

import pydantic
from prefect import flow, get_run_logger
from prefect.client.schemas.objects import State  # noqa: TC002
from prefect.states import Completed, Failed

from infrahub import config, lock
from infrahub.context import InfrahubContext  # noqa: TC001  needed for prefect flow
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.changelog.diff import DiffChangelogCollector, MigrationTracker
from infrahub.core.constants import MutationAction
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.diff_locker import DiffLocker
from infrahub.core.diff.ipam_diff_parser import IpamDiffParser
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.model.path import BranchTrackingId, EnrichedDiffRoot, EnrichedDiffRootMetadata
from infrahub.core.diff.models import RequestDiffUpdate
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.graph import GRAPH_VERSION
from infrahub.core.merge import BranchMerger
from infrahub.core.migrations.exceptions import MigrationFailureError
from infrahub.core.migrations.runner import MigrationRunner
from infrahub.core.schema.update_coordinator import MigrationExecutor, SchemaUpdateCoordinator
from infrahub.core.timestamp import Timestamp
from infrahub.core.validators.determiner import ConstraintValidatorDeterminer
from infrahub.core.validators.models.validate_migration import SchemaValidateMigrationData
from infrahub.core.validators.tasks import schema_validate_migrations
from infrahub.dependencies.registry import get_component_registry
from infrahub.events.branch_action import (
    BranchCreatedEvent,
    BranchDeletedEvent,
    BranchMergedEvent,
    BranchMigratedEvent,
    BranchRebasedEvent,
)
from infrahub.events.models import EventMeta, InfrahubEvent
from infrahub.events.node_action import get_node_event
from infrahub.exceptions import BranchNotFoundError, ValidationError
from infrahub.generators.constants import GeneratorDefinitionRunSource
from infrahub.graphql.mutations.models import BranchCreateModel  # noqa: TC001
from infrahub.workers.dependencies import get_component, get_database, get_event_service, get_workflow
from infrahub.workflows.catalogue import (
    BRANCH_CANCEL_PROPOSED_CHANGES,
    BRANCH_MERGE_POST_PROCESS,
    DIFF_REFRESH_ALL,
    DIFF_UPDATE,
    GIT_REPOSITORIES_CREATE_BRANCH,
    IPAM_RECONCILIATION,
    TRIGGER_ARTIFACT_DEFINITION_GENERATE,
    TRIGGER_GENERATOR_DEFINITION_RUN,
)
from infrahub.workflows.utils import add_tags


@flow(name="branch-migrate", flow_run_name="Apply migrations to branch {branch}")
async def migrate_branch(branch: str, context: InfrahubContext, send_events: bool = True) -> None:
    await add_tags(branches=[branch])

    database = await get_database()
    async with database.start_session() as db:
        log = get_run_logger()

        obj = await Branch.get_by_name(db=db, name=branch)

        if obj.graph_version == GRAPH_VERSION:
            log.info(f"Branch '{obj.name}' has graph version {obj.graph_version}, no migrations to apply")
            return

        migration_runner = MigrationRunner(branch=obj)
        if not migration_runner.has_migrations():
            log.info(f"No migrations detected for branch '{obj.name}'")
            obj.graph_version = GRAPH_VERSION
            await obj.save(db=db)
            return

        # Branch status will remain as so if the migration process fails
        # This will help user to know that a branch is in an invalid state to be used properly and that actions need to be taken
        if obj.status != BranchStatus.NEED_UPGRADE_REBASE:
            obj.status = BranchStatus.NEED_UPGRADE_REBASE
            await obj.save(db=db)

        try:
            log.info(f"Running migrations for branch '{obj.name}'")
            await migration_runner.run(db=db, at=Timestamp())
        except MigrationFailureError as exc:
            log.error(f"Failed to run migrations for branch '{obj.name}': {exc.errors}")
            raise

        if obj.status == BranchStatus.NEED_UPGRADE_REBASE:
            obj.status = BranchStatus.OPEN
        obj.graph_version = GRAPH_VERSION
        await obj.save(db=db)

    if send_events:
        event_service = await get_event_service()
        await event_service.send(
            BranchMigratedEvent(
                branch_name=obj.name, branch_id=str(obj.uuid), meta=EventMeta(branch=obj, context=context)
            )
        )


@flow(name="branch-rebase", flow_run_name="Rebase branch {branch}")
async def rebase_branch(branch: str, context: InfrahubContext, send_events: bool = True) -> None:  # noqa: PLR0915
    workflow = get_workflow()
    database = await get_database()
    async with database.start_session() as db:
        log = get_run_logger()
        await add_tags(branches=[branch])
        obj = await Branch.get_by_name(db=db, name=branch)
        base_branch = await Branch.get_by_name(db=db, name=registry.default_branch)
        component_registry = get_component_registry()
        diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=obj)
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=obj)
        diff_coordinator.set_logger(log)
        diff_merger = await component_registry.get_component(DiffMerger, db=db, branch=obj)
        initial_from_time = Timestamp(obj.get_branched_from())
        merger = BranchMerger(
            db=db,
            diff_coordinator=diff_coordinator,
            diff_merger=diff_merger,
            diff_repository=diff_repository,
            source_branch=obj,
            diff_locker=DiffLocker(),
            workflow=workflow,
        )

        enriched_diff_metadata = await diff_coordinator.update_branch_diff(base_branch=base_branch, diff_branch=obj)
        async for _ in diff_repository.get_all_conflicts_for_diff(
            diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
        ):
            # if there are any conflicts, raise the error
            raise ValidationError(
                f"Branch {obj.name} contains conflicts with the default branch that must be addressed."
                " Please review the diff for details and manually update the conflicts before rebasing."
            )

        # rebase to the end time of the diff in case conflicting changes happen on
        # either branch while rebasing and migrating
        rebase_at = enriched_diff_metadata.to_time
        node_diff_field_summaries = await diff_repository.get_node_field_summaries(
            diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
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
            error_messages = [
                f"{violation.message} for constraint {response.constraint_name} {response.schema_path.field_name} {response.schema_path.property_name} and node {violation.node_id} {violation.node_kind}"  # noqa: E501
                for response in responses
                for violation in response.violations
            ]

            if error_messages:
                raise ValidationError(",\n".join(error_messages))

        pre_rebase_schema = merger.destination_schema.duplicate()
        migrations = []
        async with lock.registry.global_graph_lock():
            async with db.start_transaction() as dbt:
                await obj.rebase(db=dbt, user_id=context.account.account_id, at=rebase_at)
                log.info("Branch graph rebased")

            if obj.has_schema_changes:
                # Load the updated schema from DB after rebase
                log.info("Loading rebased schema")
                updated_schema = await registry.schema.load_schema_from_db(db=db, branch=obj)

                # Calculate migrations before updating registry
                log.info("Calculating migrations")
                migrations = await merger.calculate_migrations(target_schema=updated_schema)

                # Use coordinator to update registry and run migrations with rollback on failure
                log.info("Running migrations")
                coordinator = SchemaUpdateCoordinator(
                    db=db,
                    branch=obj,
                    schema_manager=registry.schema,
                    origin_schema=pre_rebase_schema,
                    workflow=workflow,
                    context=context,
                    migration_executor=MigrationExecutor.WORKFLOW if send_events else MigrationExecutor.DIRECT,
                    logger=log,
                )
                await coordinator.execute(
                    candidate_schema=updated_schema,
                    at=rebase_at,
                    migrations=migrations,
                    update_db=False,
                    update_registry=True,
                    user_id=context.account.account_id,
                )
                log.info("Migrations completed")

        default_branch_diff = await _get_diff_root(
            diff_coordinator=diff_coordinator,
            enriched_diff_metadata=enriched_diff_metadata,
            diff_repository=diff_repository,
            base_branch=base_branch,
            target_from=initial_from_time,
        )

        # -------------------------------------------------------------
        # Trigger the reconciliation of IPAM data after the rebase
        # -------------------------------------------------------------
        diff_parser = await component_registry.get_component(IpamDiffParser, db=db, branch=obj)
        ipam_node_details = await diff_parser.get_changed_ipam_node_details(
            source_branch_name=obj.name,
            target_branch_name=registry.default_branch,
        )
        if ipam_node_details:
            await workflow.submit_workflow(
                workflow=IPAM_RECONCILIATION,
                context=context,
                parameters={"branch": obj.name, "ipam_node_details": ipam_node_details},
            )

    await migrate_branch(branch=branch, context=context, send_events=send_events)
    await workflow.submit_workflow(workflow=DIFF_REFRESH_ALL, context=context, parameters={"branch_name": obj.name})

    if not send_events:
        return

    # -------------------------------------------------------------
    # Generate an event to indicate that a branch has been rebased
    # -------------------------------------------------------------
    rebase_event = BranchRebasedEvent(
        branch_name=obj.name, branch_id=str(obj.uuid), meta=EventMeta(branch=obj, context=context)
    )
    events: list[InfrahubEvent] = [rebase_event]
    changelog_collector = DiffChangelogCollector(
        diff=default_branch_diff, branch=obj, db=db, migration_tracker=MigrationTracker(migrations=migrations)
    )
    for action, node_changelog in changelog_collector.collect_changelogs():
        node_event_class = get_node_event(MutationAction.from_diff_action(diff_action=action))
        mutate_event = node_event_class(
            kind=node_changelog.node_kind,
            node_id=node_changelog.node_id,
            changelog=node_changelog,
            fields=node_changelog.updated_fields,
            meta=EventMeta.from_parent(parent=rebase_event, branch=obj),
        )
        events.append(mutate_event)

    event_service = await get_event_service()
    for event in events:
        await event_service.send(event)


@flow(name="branch-merge", flow_run_name="Merge branch {branch} into main")
async def merge_branch(branch: str, context: InfrahubContext, proposed_change_id: str | None = None) -> None:
    database = await get_database()
    async with database.start_session() as db:
        log = get_run_logger()

        await add_tags(branches=[branch, registry.default_branch])

        obj = await Branch.get_by_name(db=db, name=branch)
        default_branch = await registry.get_branch(db=db, branch=registry.default_branch)
        component_registry = get_component_registry()
        merge_event = BranchMergedEvent(
            branch_name=obj.name,
            branch_id=str(obj.get_uuid()),
            proposed_change_id=proposed_change_id,
            meta=EventMeta.from_context(context=context, branch=registry.get_global_branch()),
        )

        merger: BranchMerger | None = None
        workflow = get_workflow()
        merge_at = Timestamp()
        pre_merge_schema = registry.schema.get_schema_branch(name=registry.default_branch).duplicate()
        async with lock.registry.global_graph_lock():
            diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=obj)
            diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=obj)
            diff_merger = await component_registry.get_component(DiffMerger, db=db, branch=obj)
            merger = BranchMerger(
                db=db,
                diff_coordinator=diff_coordinator,
                diff_merger=diff_merger,
                diff_repository=diff_repository,
                source_branch=obj,
                diff_locker=DiffLocker(),
                workflow=workflow,
            )
            branch_diff = await merger.merge(at=merge_at)

        changelog_collector = DiffChangelogCollector(diff=branch_diff, branch=obj, db=db)
        node_events = changelog_collector.collect_changelogs()

        # Handle schema updates and migrations after merge
        if merger and await merger.has_schema_changes():
            # Load the updated schema from DB after merge
            log.info("Loading updated schema")
            updated_schema = await registry.schema.load_schema_from_db(
                db=db,
                branch=merger.destination_branch,
            )
            log.info("Calculating migrations")
            migrations = await merger.calculate_migrations(target_schema=updated_schema)

            # Use coordinator to update registry and run migrations with rollback on failure
            log.info("Running migrations")
            coordinator = SchemaUpdateCoordinator(
                db=db,
                branch=merger.destination_branch,
                schema_manager=registry.schema,
                origin_schema=pre_merge_schema,
                workflow=workflow,
                context=context,
                migration_executor=MigrationExecutor.WORKFLOW,
                logger=log,
            )
            await coordinator.execute(
                candidate_schema=updated_schema,
                at=merge_at,
                migrations=migrations,
                update_db=False,  # Schema nodes already written by merge
                update_registry=True,
                user_id=context.account.account_id,
            )
            log.info("Migrations completed")
        # -------------------------------------------------------------
        # Trigger the reconciliation of IPAM data after the merge
        # -------------------------------------------------------------
        diff_parser = await component_registry.get_component(IpamDiffParser, db=db, branch=obj)
        ipam_node_details = await diff_parser.get_changed_ipam_node_details(
            source_branch_name=obj.name,
            target_branch_name=registry.default_branch,
        )
        if ipam_node_details:
            await get_workflow().submit_workflow(
                workflow=IPAM_RECONCILIATION,
                context=context,
                parameters={"branch": registry.default_branch, "ipam_node_details": ipam_node_details},
            )
        # -------------------------------------------------------------
        # remove tracking ID from the diff because there is no diff after the merge
        # -------------------------------------------------------------
        diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=obj)
        await diff_repository.mark_tracking_ids_merged(tracking_ids=[BranchTrackingId(name=obj.name)])

        # -------------------------------------------------------------
        # Set branch status to MERGED to make it read-only
        # -------------------------------------------------------------
        obj.status = BranchStatus.MERGED
        await obj.save(db=db)
        registry.branch[obj.name] = obj

        # -------------------------------------------------------------
        # Cancel any remaining open proposed changes for this merged branch
        # -------------------------------------------------------------
        await get_workflow().submit_workflow(
            workflow=BRANCH_CANCEL_PROPOSED_CHANGES,
            context=context,
            parameters={"branch_name": obj.name},
        )

        # -------------------------------------------------------------
        # Generate an event to indicate that a branch has been merged
        # NOTE: we still need to convert this event and potentially pull
        #   some tasks currently executed based on the event into this workflow
        # -------------------------------------------------------------
        await get_workflow().submit_workflow(
            workflow=BRANCH_MERGE_POST_PROCESS,
            context=context,
            parameters={"source_branch": obj.name, "target_branch": registry.default_branch},
        )

        events: list[InfrahubEvent] = [merge_event]

        for action, node_changelog in node_events:
            meta = EventMeta.from_parent(parent=merge_event, branch=default_branch)
            node_event_class = get_node_event(MutationAction.from_diff_action(diff_action=action))
            mutate_event = node_event_class(
                kind=node_changelog.node_kind,
                node_id=node_changelog.node_id,
                changelog=node_changelog,
                fields=node_changelog.updated_fields,
                meta=meta,
            )
            events.append(mutate_event)

        event_service = await get_event_service()
        for event in events:
            await event_service.send(event=event)


@flow(name="branch-delete", flow_run_name="Delete branch {branch}")
async def delete_branch(branch: str, context: InfrahubContext) -> None:
    await add_tags(branches=[branch])

    database = await get_database()
    async with database.start_session() as db:
        obj = await Branch.get_by_name(db=db, name=str(branch))
        await obj.delete(db=db)

        event = BranchDeletedEvent(
            branch_name=branch,
            branch_id=str(obj.uuid),
            sync_with_git=obj.sync_with_git,
            meta=EventMeta.from_context(context=context, branch=registry.get_global_branch()),
        )

        await get_workflow().submit_workflow(
            workflow=BRANCH_CANCEL_PROPOSED_CHANGES, context=context, parameters={"branch_name": branch}
        )

        event_service = await get_event_service()
        await event_service.send(event=event)


@flow(
    name="branch-validate",
    flow_run_name="Validate branch {branch} for conflicts",
    description="Validate if the branch has some conflicts",
    persist_result=True,
)
async def validate_branch(branch: str) -> State:
    await add_tags(branches=[branch])

    database = await get_database()
    async with database.start_session() as db:
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
async def create_branch(model: BranchCreateModel, context: InfrahubContext) -> None:
    await add_tags(branches=[model.name])

    database = await get_database()
    async with database.start_session() as db:
        try:
            await Branch.get_by_name(db=db, name=model.name)
            raise ValidationError(f"The branch {model.name} already exists")
        except BranchNotFoundError:
            pass

        data_dict: dict[str, Any] = dict(model)
        data_dict.pop("is_isolated", None)

        try:
            obj = Branch(**data_dict)
        except pydantic.ValidationError as exc:
            error_msgs = [f"invalid field {error['loc'][0]}: {error['msg']}" for error in exc.errors()]
            raise ValidationError("\n".join(error_msgs)) from exc

        async with lock.registry.local_schema_lock():
            # Copy the schema from the origin branch and set the hash and the schema_changed_at value
            origin_schema = registry.schema.get_schema_branch(name=obj.origin_branch)
            new_schema = origin_schema.duplicate(name=obj.name)
            registry.schema.set_schema_branch(name=obj.name, schema=new_schema)
            obj.update_schema_hash()
            await obj.save(db=db, user_id=context.account.account_id)

            # Add Branch to registry
            registry.branch[obj.name] = obj
            component = await get_component()
            await component.refresh_schema_hash(branches=[obj.name])

        event = BranchCreatedEvent(
            branch_name=obj.name,
            branch_id=str(obj.uuid),
            sync_with_git=obj.sync_with_git,
            meta=EventMeta.from_context(context=context, branch=registry.get_global_branch()),
        )
        event_service = await get_event_service()
        await event_service.send(event=event)

        if obj.sync_with_git:
            await get_workflow().submit_workflow(
                workflow=GIT_REPOSITORIES_CREATE_BRANCH,
                context=context,
                parameters={"branch": obj.name, "branch_id": str(obj.uuid)},
            )


async def _get_diff_root(
    diff_coordinator: DiffCoordinator,
    enriched_diff_metadata: EnrichedDiffRootMetadata,
    diff_repository: DiffRepository,
    base_branch: Branch,
    target_from: Timestamp,
) -> EnrichedDiffRoot:
    default_branch_diff = await diff_coordinator.create_or_update_arbitrary_timeframe_diff(
        base_branch=base_branch,
        diff_branch=base_branch,
        from_time=target_from,
        to_time=enriched_diff_metadata.to_time,
        name=str(uuid4()),
    )
    # make sure we have the actual diff with data and not just the metadata
    if not isinstance(default_branch_diff, EnrichedDiffRoot):
        default_branch_diff = await diff_repository.get_one(
            diff_branch_name=base_branch.name, diff_id=default_branch_diff.uuid
        )

    return default_branch_diff


@flow(
    name="branch-merge-post-process",
    flow_run_name="Run additional tasks after merging {source_branch} in {target_branch}",
)
async def post_process_branch_merge(source_branch: str, target_branch: str, context: InfrahubContext) -> None:
    database = await get_database()
    async with database.start_session() as db:
        await add_tags(branches=[source_branch])
        log = get_run_logger()
        log.info(f"Running additional tasks after merging {source_branch} within {target_branch}")

        component_registry = get_component_registry()
        default_branch = registry.get_branch_from_registry()
        diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=default_branch)

        await get_workflow().submit_workflow(
            workflow=TRIGGER_ARTIFACT_DEFINITION_GENERATE,
            context=context,
            parameters={"branch": target_branch},
        )

        await get_workflow().submit_workflow(
            workflow=TRIGGER_GENERATOR_DEFINITION_RUN,
            context=context,
            parameters={"branch": target_branch, "source": GeneratorDefinitionRunSource.MERGE},
        )

        if not config.SETTINGS.main.diff_update_after_merge:
            return

        # send diff update requests for every active branch-tracking diff
        active_branches = await Branch.get_list(db=db)
        active_branch_names = {branch.name for branch in active_branches}
        diff_roots = await diff_repository.get_roots_metadata(base_branch_names=[target_branch])
        for diff_root in diff_roots:
            if (
                isinstance(diff_root.tracking_id, BranchTrackingId)
                and not diff_root.is_frozen
                and diff_root.base_branch_name != diff_root.diff_branch_name
                and diff_root.diff_branch_name in active_branch_names
            ):
                request_diff_update_model = RequestDiffUpdate(branch_name=diff_root.diff_branch_name)
                await get_workflow().submit_workflow(
                    workflow=DIFF_UPDATE, context=context, parameters={"model": request_diff_update_model}
                )
