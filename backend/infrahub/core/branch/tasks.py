from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from prefect import flow, get_run_logger
from prefect.client.schemas.objects import State  # noqa: TC002
from prefect.states import Completed, Failed

from infrahub import config, lock
from infrahub.context import InfrahubContext  # noqa: TC001  needed for prefect flow
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.branch.creator import BranchCreator
from infrahub.core.branch.data_deleter import BranchDataDeleter
from infrahub.core.branch.delete_coordinator import BranchDeleteOrchestrator
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.changelog.diff import DiffChangelogCollector, MigrationTracker
from infrahub.core.constants import MutationAction
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.ipam_diff_parser import IpamDiffParser
from infrahub.core.diff.model.path import BranchTrackingId, EnrichedDiffRoot, EnrichedDiffRootMetadata
from infrahub.core.diff.models import RequestDiffUpdate
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.diff.summary_cache import DiffSummaryCache
from infrahub.core.diff.summary_serializer import DiffSummarySerializer
from infrahub.core.graph import GRAPH_VERSION
from infrahub.core.merge.builder import build_branch_merge_orchestrator
from infrahub.core.merge.merge_locker import MergeLocker
from infrahub.core.merge.python_target_sources import build_python_target_deriver
from infrahub.core.merge.recompute_coalescing import (
    CoalescedRecomputeBuilder,
    CoalescedRecomputeSubmitter,
    MergeChange,
    MergeRecomputeCoordinator,
)
from infrahub.core.merge.regeneration_dispatcher import PostMergeRegenerationDispatcher, submit_full_regeneration
from infrahub.core.merge.schema_analyzer import MergeSchemaAnalyzer
from infrahub.core.merge.selective_regen.generator_output import (
    GeneratorCascadeOutput,
    GeneratorTrackingGroupDiffCapturer,
)
from infrahub.core.merge.selective_regen.orchestrator import build_merge_selective_regeneration
from infrahub.core.merge.write_blocker import MergeWriteBlocker
from infrahub.core.migrations.exceptions import MigrationFailureError
from infrahub.core.migrations.runner import MigrationRunner
from infrahub.core.rollback import GraphRollbacker
from infrahub.core.schema.update_coordinator import MigrationExecutor, SchemaUpdateCoordinator
from infrahub.core.timestamp import Timestamp
from infrahub.core.validators.constraint_merge import build_constraint_info_merger
from infrahub.core.validators.determiner import build_constraint_validator_determiner
from infrahub.core.validators.models.validate_migration import SchemaValidateMigrationData
from infrahub.core.validators.tasks import schema_validate_migrations
from infrahub.dependencies.registry import get_component_registry
from infrahub.events.branch_action import (
    BranchMigratedEvent,
    BranchRebasedEvent,
)
from infrahub.events.constants import NodeMutationOrigin
from infrahub.events.models import EventMeta, InfrahubEvent
from infrahub.events.node_action import get_node_event
from infrahub.exceptions import ValidationError
from infrahub.graphql.mutations.models import BranchCreateModel  # noqa: TC001
from infrahub.utils import log_exception_guard
from infrahub.workers.dependencies import (
    get_cache,
    get_client,
    get_component,
    get_database,
    get_event_service,
    get_workflow,
)
from infrahub.workflows.catalogue import (
    DIFF_REFRESH_ALL,
    DIFF_UPDATE,
    IPAM_RECONCILIATION,
)
from infrahub.workflows.constants import WorkflowPriority
from infrahub.workflows.utils import add_tags

if TYPE_CHECKING:
    from logging import Logger, LoggerAdapter

    from infrahub.core.models import SchemaUpdateConstraintInfo
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


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
        event_context = context.to_event_context()
        event_service = await get_event_service()
        await event_service.send(
            BranchMigratedEvent(
                branch_name=obj.name,
                branch_id=str(obj.uuid),
                meta=EventMeta(branch=obj, context=event_context),
            )
        )


@flow(name="branch-rebase", flow_run_name="Rebase branch {branch}")
async def rebase_branch(branch: str, context: InfrahubContext, send_events: bool = True) -> None:  # noqa: PLR0915
    workflow = get_workflow()
    database = await get_database()
    merge_write_blocker = MergeWriteBlocker(cache=await get_cache())

    medium_context = context.model_copy(update={"priority": WorkflowPriority.MEDIUM})
    low_context = context.model_copy(update={"priority": WorkflowPriority.LOW})

    async with database.start_session() as db:
        log = get_run_logger()
        await add_tags(branches=[branch])

        protection = await merge_write_blocker.get()
        if protection is not None:
            raise ValidationError("Cannot rebase a branch while a merge is in progress.")

        user_branch = await Branch.get_by_name(db=db, name=branch)
        base_branch = await Branch.get_by_name(db=db, name=registry.default_branch)
        component_registry = get_component_registry()
        diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=user_branch)
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=user_branch)
        diff_coordinator.set_logger(log)
        initial_from_time = Timestamp(user_branch.get_branched_from())
        schema_analyzer = MergeSchemaAnalyzer(
            db=db,
            source_branch=user_branch,
            destination_branch=base_branch,
            diff_repository=diff_repository,
            schema_manager=registry.schema,
        )
        schema_update_coordinator = SchemaUpdateCoordinator(
            db=db,
            schema_manager=registry.schema,
            rollbacker=GraphRollbacker(db=db),
            workflow=workflow,
            logger=log,
        )

        enriched_diff_metadata = await diff_coordinator.update_branch_diff(
            base_branch=base_branch, diff_branch=user_branch
        )
        async for _ in diff_repository.get_all_conflicts_for_diff(
            diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
        ):
            # if there are any conflicts, raise the error
            raise ValidationError(
                f"Branch {user_branch.name} contains conflicts with the default branch that must be addressed."
                " Please review the diff for details and manually update the conflicts before rebasing."
            )

        # rebase to the end time of the diff in case conflicting changes happen on
        # either branch while rebasing and migrating
        rebase_at = enriched_diff_metadata.to_time
        node_diff_field_summaries = await diff_repository.get_node_field_summaries(
            diff_branch_name=enriched_diff_metadata.diff_branch_name, diff_id=enriched_diff_metadata.uuid
        )

        candidate_schema = schema_analyzer.get_candidate_schema()
        determiner = build_constraint_validator_determiner(db=db, branch=user_branch, at=rebase_at)
        data_diff_constraints = await determiner.get_constraints(
            schema_branch=candidate_schema, node_diffs=node_diff_field_summaries
        )

        # If there are some changes related to the schema between this branch and main, we need to
        #  - Run all the validations to ensure everything is correct before rebasing the branch
        #  - Run all the migrations after the rebase
        schema_diff_constraints: list[SchemaUpdateConstraintInfo] = []
        if user_branch.schema_differs_from_default_branch:
            schema_diff_constraints = await schema_analyzer.calculate_validations(target_schema=candidate_schema)
        merger = build_constraint_info_merger()
        constraints = merger.merge(candidate_schema, data_diff_constraints, schema_diff_constraints)
        if constraints:
            responses = await schema_validate_migrations(
                message=SchemaValidateMigrationData(
                    branch=user_branch, schema_branch=candidate_schema, constraints=constraints
                )
            )
            error_messages = [
                f"{violation.message} for constraint {response.constraint_name} {response.schema_path.field_name} {response.schema_path.property_name} and node {violation.node_id} {violation.node_kind}"  # noqa: E501
                for response in responses
                for violation in response.violations
            ]

            if error_messages:
                raise ValidationError(",\n".join(error_messages))

        migrations = []
        async with lock.registry.global_graph_lock():
            # Both baselines are resolved under the lock and before the rebase: the common ancestor
            # resolves against branched_from, which the rebase advances, and the rollback snapshot
            # must not predate a schema update that landed while the pre-lock validation ran.
            migration_baseline_schema: SchemaBranch | None = None
            pre_rebase_schema: SchemaBranch | None = None
            if user_branch.schema_differs_from_default_branch:
                migration_baseline_schema = (await schema_analyzer.get_common_ancestor_schema()).duplicate()
                pre_rebase_schema = registry.schema.get_schema_branch(name=user_branch.name).duplicate()

            async with db.start_transaction() as dbt:
                await user_branch.rebase(db=dbt, user_id=context.account.account_id, at=rebase_at)
                log.info("Branch graph rebased")

            # Only update registry after txn commit. Otherwise, branch status and branched_from
            # could diverge between registry and database during a failed txn commit.
            registry.branch[user_branch.name] = user_branch

            if migration_baseline_schema is not None and pre_rebase_schema is not None:
                # Update the registry and run migrations after the rebase, with rollback on failure.
                # Schema nodes were already written by the rebase, so load that schema and apply only
                # the migrations it implies.
                log.info("Running migrations")
                rebased_schema = await registry.schema.load_schema_from_db(db=db, branch=user_branch)
                migrations = await schema_analyzer.calculate_migrations(target_schema=rebased_schema)
                # The schema migrations need a unique timestamp so that a rollback on failure will
                # not try to erase changes made during the graph rebase and destroy the branch.
                migration_at = rebase_at.add(microseconds=1)
                await schema_update_coordinator.execute(
                    branch=user_branch,
                    origin_schema=migration_baseline_schema,
                    rollback_schema=pre_rebase_schema,
                    candidate_schema=rebased_schema,
                    at=migration_at,
                    context=context,
                    migration_executor=MigrationExecutor.WORKFLOW if send_events else MigrationExecutor.DIRECT,
                    migrations=migrations,
                    update_db=False,
                    update_registry=True,
                    user_id=context.account.account_id,
                    manage_rollback=True,
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
        diff_parser = await component_registry.get_component(IpamDiffParser, db=db, branch=user_branch)
        ipam_node_details = await diff_parser.get_changed_ipam_node_details(
            source_branch_name=user_branch.name,
            target_branch_name=registry.default_branch,
        )
        if ipam_node_details:
            await workflow.submit_workflow(
                workflow=IPAM_RECONCILIATION,
                context=medium_context,
                parameters={"branch": user_branch.name, "ipam_node_details": ipam_node_details},
            )

    await migrate_branch(branch=branch, context=context, send_events=send_events)
    await workflow.submit_workflow(
        workflow=DIFF_REFRESH_ALL, context=low_context, parameters={"branch_name": user_branch.name}
    )

    if not send_events:
        return

    # -------------------------------------------------------------
    # Generate an event to indicate that a branch has been rebased
    # -------------------------------------------------------------
    event_context = context.to_event_context()
    rebase_event = BranchRebasedEvent(
        branch_name=user_branch.name,
        branch_id=str(user_branch.uuid),
        meta=EventMeta(branch=user_branch, context=event_context),
    )
    events: list[InfrahubEvent] = [rebase_event]
    changes: list[MergeChange] = []
    changelog_collector = DiffChangelogCollector(
        diff=default_branch_diff, branch=user_branch, db=db, migration_tracker=MigrationTracker(migrations=migrations)
    )
    for action, node_changelog in changelog_collector.collect_changelogs():
        mutation_action = MutationAction.from_diff_action(diff_action=action)
        meta = EventMeta.from_parent(parent=rebase_event, branch=user_branch)
        meta.origin = NodeMutationOrigin.REBASE
        mutate_event = get_node_event(mutation_action)(
            kind=node_changelog.node_kind,
            node_id=node_changelog.node_id,
            changelog=node_changelog,
            fields=node_changelog.updated_fields,
            meta=meta,
        )
        events.append(mutate_event)
        changes.append(
            MergeChange(
                node_id=node_changelog.node_id,
                kind=node_changelog.node_kind,
                action=mutation_action.value,
                changed_fields=frozenset(node_changelog.updated_fields),
            )
        )

    event_service = await get_event_service()
    for event in events:
        await event_service.send(event)

    with log_exception_guard(log, "Failed to submit the coalesced post-rebase recompute"):
        schema_name = (
            user_branch.name if user_branch.name in registry.get_altered_schema_branches() else registry.default_branch
        )
        schema_branch = registry.schema.get_schema_branch(name=schema_name)
        coordinator = MergeRecomputeCoordinator(
            builder=CoalescedRecomputeBuilder(schema_branch=schema_branch),
            submitter=CoalescedRecomputeSubmitter(workflow=get_workflow()),
            python_deriver=await build_python_target_deriver(db=db),
        )
        await coordinator.run(changes=changes, branch=user_branch.name, context=event_context)


@flow(name="branch-merge", flow_run_name="Merge branch {branch} into main")
async def merge_branch(branch: str, context: InfrahubContext, proposed_change_id: str | None = None) -> None:
    log = get_run_logger()
    await add_tags(branches=[branch, registry.default_branch])

    database = await get_database()
    async with database.start_session() as db:
        # Hold the global merge lock for the whole flow and load the branch under it, so the merge
        # decision and the orchestrator operate on branch state that cannot change mid-merge.
        log.info("Acquiring global merge lock")
        async with MergeLocker().acquire_global_lock():
            log.info("Global merge lock acquired")
            source_branch = await Branch.get_by_name(db=db, name=branch)
            if source_branch.status != BranchStatus.OPEN:
                log.info(f"Branch '{branch}' is not open (status={source_branch.status}), skipping merge")
                return

            destination_branch = await registry.get_branch(db=db, branch=registry.default_branch)
            await _do_merge_branch(
                db=db,
                source_branch=source_branch,
                destination_branch=destination_branch,
                context=context,
                proposed_change_id=proposed_change_id,
                log=log,
            )


async def _do_merge_branch(
    *,
    db: InfrahubDatabase,
    source_branch: Branch,
    destination_branch: Branch,
    context: InfrahubContext,
    proposed_change_id: str | None,
    log: Logger | LoggerAdapter[Logger],
) -> None:
    """Run the merge body for an OPEN source branch."""
    orchestrator = await build_branch_merge_orchestrator(
        db=db, source_branch=source_branch, destination_branch=destination_branch, logger=log
    )
    await orchestrator.merge(context=context, proposed_change_id=proposed_change_id)


@flow(name="branch-delete", flow_run_name="Delete branch {branch}")
async def delete_branch(
    branch: str, context: InfrahubContext, delete_from_git: bool = False, proposed_change_id: str | None = None
) -> None:
    await add_tags(branches=[branch], nodes=[proposed_change_id] if proposed_change_id else None)
    database = await get_database()
    workflow = get_workflow()
    event_service = await get_event_service()
    async with database.start_session() as db:
        # ignore_deleting=False so that a delete which failed part way through can be run again:
        obj = await Branch.get_by_name(db=db, name=str(branch), ignore_deleting=False)

        component_registry = get_component_registry()
        diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=obj)

        log = get_run_logger()
        orchestrator = BranchDeleteOrchestrator(
            data_deleter=BranchDataDeleter(db=db, batch_size=config.SETTINGS.database.query_size_limit, log=log),
            diff_freezer=diff_repository,
            event_service=event_service,
            workflow=workflow,
            log=log,
            global_branch=registry.get_global_branch(),
            delete_git_branch_after_merge=config.SETTINGS.git.delete_git_branch_after_merge,
        )
        low_context = context.model_copy(update={"priority": WorkflowPriority.LOW})
        await orchestrator.delete(
            branch=obj,
            context=low_context,
            delete_from_git=delete_from_git,
            proposed_change_id=proposed_change_id,
        )


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
    component = await get_component()
    event_service = await get_event_service()
    workflow = get_workflow()

    async with database.start_session() as db:
        creator = BranchCreator(
            db=db,
            lock_registry=lock.registry,
            component=component,
            event_service=event_service,
            workflow=workflow,
        )
        await creator.create(model=model, context=context)


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


async def _build_post_merge_regeneration_dispatcher(
    db: InfrahubDatabase,
    branch: Branch,
    log: Logger | LoggerAdapter[Logger],
) -> PostMergeRegenerationDispatcher:
    component_registry = get_component_registry()
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
    diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=branch)
    output_capturer = GeneratorTrackingGroupDiffCapturer(
        diff_coordinator=diff_coordinator,
        diff_repository=diff_repository,
        serializer=DiffSummarySerializer(),
        client=get_client(),
        branch=branch,
    )
    generator_output = GeneratorCascadeOutput(capturer=output_capturer)
    return PostMergeRegenerationDispatcher(
        workflow=get_workflow(),
        planner=build_merge_selective_regeneration(client=get_client(), log=log, generator_output=generator_output),
        summary_cache=DiffSummaryCache(
            cache=await get_cache(), serializer=DiffSummarySerializer(), key_namespace="branch_merge"
        ),
        log=log,
    )


@flow(
    name="branch-merge-post-process",
    flow_run_name="Run additional tasks after merging {source_branch} in {target_branch}",
)
async def post_process_branch_merge(
    source_branch: str,
    target_branch: str,
    context: InfrahubContext,
    merge_diff_cache_key: str | None = None,
) -> None:
    database = await get_database()
    async with database.start_session() as db:
        await add_tags(branches=[source_branch])
        log = get_run_logger()
        log.info(f"Running additional tasks after merging {source_branch} within {target_branch}")

        component_registry = get_component_registry()
        default_branch = registry.get_branch_from_registry()
        diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=default_branch)

        if config.SETTINGS.main.selective_execution_after_merge:
            target_branch_obj = await Branch.get_by_name(db=db, name=target_branch)
            dispatcher = await _build_post_merge_regeneration_dispatcher(db=db, branch=target_branch_obj, log=log)
            await dispatcher.dispatch(
                context=context,
                target_branch=target_branch,
                merge_diff_cache_key=merge_diff_cache_key,
            )
        else:
            await submit_full_regeneration(workflow=get_workflow(), context=context, target_branch=target_branch)

        if not config.SETTINGS.main.diff_update_after_merge:
            return

        # send diff update requests for every active branch-tracking diff
        active_branches = await Branch.get_list(db=db)
        active_branch_names = {branch.name for branch in active_branches}
        diff_roots = await diff_repository.get_roots_metadata(base_branch_names=[target_branch])
        for diff_root in diff_roots:
            if (
                diff_root.base_branch_name != diff_root.diff_branch_name
                and diff_root.diff_branch_name in active_branch_names
                and isinstance(diff_root.tracking_id, BranchTrackingId)
                and not diff_root.is_frozen
            ):
                request_diff_update_model = RequestDiffUpdate(branch_name=diff_root.diff_branch_name)
                await get_workflow().submit_workflow(
                    workflow=DIFF_UPDATE, context=context, parameters={"model": request_diff_update_model}
                )
