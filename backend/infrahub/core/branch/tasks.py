from __future__ import annotations

from uuid import uuid4

from prefect import flow, get_run_logger
from prefect.client.schemas.objects import State  # noqa: TC002
from prefect.states import Completed, Failed

from infrahub import config, lock
from infrahub.context import InfrahubContext  # noqa: TC001  needed for prefect flow
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.branch.creator import BranchCreator
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.changelog.diff import DiffChangelogCollector, MigrationTracker
from infrahub.core.constants import MutationAction
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.ipam_diff_parser import IpamDiffParser
from infrahub.core.diff.model.path import BranchTrackingId, EnrichedDiffRoot, EnrichedDiffRootMetadata
from infrahub.core.diff.models import RequestDiffUpdate
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.graph import GRAPH_VERSION
from infrahub.core.merge.builder import build_branch_merge_orchestrator
from infrahub.core.merge.schema_analyzer import MergeSchemaAnalyzer
from infrahub.core.merge.write_blocker import MergeWriteBlocker
from infrahub.core.migrations.exceptions import MigrationFailureError
from infrahub.core.migrations.runner import MigrationRunner
from infrahub.core.schema.update_coordinator import MigrationExecutor, SchemaUpdateCoordinator
from infrahub.core.timestamp import Timestamp
from infrahub.core.validators.determiner import ConstraintValidatorDeterminer
from infrahub.core.validators.models.validate_migration import SchemaValidateMigrationData
from infrahub.core.validators.tasks import schema_validate_migrations
from infrahub.dependencies.registry import get_component_registry
from infrahub.events.branch_action import (
    BranchDeletedEvent,
    BranchMigratedEvent,
    BranchRebasedEvent,
)
from infrahub.events.models import EventMeta, InfrahubEvent
from infrahub.events.node_action import get_node_event
from infrahub.exceptions import ValidationError
from infrahub.generators.constants import GeneratorDefinitionRunSource
from infrahub.graphql.mutations.models import BranchCreateModel  # noqa: TC001
from infrahub.workers.dependencies import get_cache, get_component, get_database, get_event_service, get_workflow
from infrahub.workflows.catalogue import (
    BRANCH_CANCEL_PROPOSED_CHANGES,
    DIFF_REFRESH_ALL,
    DIFF_UPDATE,
    GIT_REPOSITORIES_DELETE_BRANCH,
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
            db=db, schema_manager=registry.schema, workflow=workflow, logger=log
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
        determiner = ConstraintValidatorDeterminer(schema_branch=candidate_schema)
        constraints = await determiner.get_constraints(node_diffs=node_diff_field_summaries)

        # If there are some changes related to the schema between this branch and main, we need to
        #  - Run all the validations to ensure everything is correct before rebasing the branch
        #  - Run all the migrations after the rebase
        if user_branch.has_schema_changes:
            constraints += await schema_analyzer.calculate_validations(target_schema=candidate_schema)
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

        pre_rebase_schema = schema_analyzer.destination_schema.duplicate()
        migrations = []
        async with lock.registry.global_graph_lock():
            async with db.start_transaction() as dbt:
                await user_branch.rebase(db=dbt, user_id=context.account.account_id, at=rebase_at)
                log.info("Branch graph rebased")

            if user_branch.has_schema_changes:
                # Update the registry and run migrations after the rebase, with rollback on failure.
                # Schema nodes were already written by the rebase, so load that schema and apply only
                # the migrations it implies.
                log.info("Running migrations")
                rebased_schema = await registry.schema.load_schema_from_db(db=db, branch=user_branch)
                migrations = await schema_analyzer.calculate_migrations(target_schema=rebased_schema)
                await schema_update_coordinator.execute(
                    branch=user_branch,
                    origin_schema=pre_rebase_schema,
                    candidate_schema=rebased_schema,
                    at=rebase_at,
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
                context=context,
                parameters={"branch": user_branch.name, "ipam_node_details": ipam_node_details},
            )

    await migrate_branch(branch=branch, context=context, send_events=send_events)
    await workflow.submit_workflow(
        workflow=DIFF_REFRESH_ALL, context=context, parameters={"branch_name": user_branch.name}
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
    changelog_collector = DiffChangelogCollector(
        diff=default_branch_diff, branch=user_branch, db=db, migration_tracker=MigrationTracker(migrations=migrations)
    )
    for action, node_changelog in changelog_collector.collect_changelogs():
        node_event_class = get_node_event(MutationAction.from_diff_action(diff_action=action))
        mutate_event = node_event_class(
            kind=node_changelog.node_kind,
            node_id=node_changelog.node_id,
            changelog=node_changelog,
            fields=node_changelog.updated_fields,
            meta=EventMeta.from_parent(parent=rebase_event, branch=user_branch),
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

        source_branch = await Branch.get_by_name(db=db, name=branch)
        destination_branch = await registry.get_branch(db=db, branch=registry.default_branch)

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
    async with database.start_session() as db:
        obj = await Branch.get_by_name(db=db, name=str(branch))

        component_registry = get_component_registry()
        diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=obj)
        await diff_repository.freeze_diffs_for_branch(branch_name=branch)

        await obj.delete(db=db)

        event_context = context.to_event_context()
        event = BranchDeletedEvent(
            branch_name=branch,
            branch_id=str(obj.uuid),
            sync_with_git=obj.sync_with_git,
            meta=EventMeta.from_context(context=event_context, branch=registry.get_global_branch()),
            proposed_change_id=proposed_change_id,
        )

        await get_workflow().submit_workflow(
            workflow=BRANCH_CANCEL_PROPOSED_CHANGES, context=context, parameters={"branch_name": branch}
        )

        event_service = await get_event_service()
        await event_service.send(event=event)

    should_delete_git = (config.SETTINGS.git.delete_git_branch_after_merge or delete_from_git) and obj.sync_with_git
    if should_delete_git:
        await get_workflow().submit_workflow(
            workflow=GIT_REPOSITORIES_DELETE_BRANCH,
            context=context,
            parameters={"branch": branch},
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
                diff_root.base_branch_name != diff_root.diff_branch_name
                and diff_root.diff_branch_name in active_branch_names
                and isinstance(diff_root.tracking_id, BranchTrackingId)
                and not diff_root.is_frozen
            ):
                request_diff_update_model = RequestDiffUpdate(branch_name=diff_root.diff_branch_name)
                await get_workflow().submit_workflow(
                    workflow=DIFF_UPDATE, context=context, parameters={"model": request_diff_update_model}
                )
