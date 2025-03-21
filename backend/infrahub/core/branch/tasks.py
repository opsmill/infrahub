from __future__ import annotations

from typing import Any
from uuid import uuid4

import pydantic
from prefect import flow, get_run_logger
from prefect.client.schemas.objects import State  # noqa: TC002
from prefect.states import Completed, Failed

from infrahub import lock
from infrahub.context import InfrahubContext  # noqa: TC001  needed for prefect flow
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.changelog.diff import DiffChangelogCollector, MigrationTracker
from infrahub.core.constants import MutationAction
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.ipam_diff_parser import IpamDiffParser
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.model.path import BranchTrackingId, EnrichedDiffRoot, EnrichedDiffRootMetadata
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.merge import BranchMerger
from infrahub.core.migrations.schema.models import SchemaApplyMigrationData
from infrahub.core.migrations.schema.tasks import schema_apply_migrations
from infrahub.core.timestamp import Timestamp
from infrahub.core.validators.determiner import ConstraintValidatorDeterminer
from infrahub.core.validators.models.validate_migration import SchemaValidateMigrationData
from infrahub.core.validators.tasks import schema_validate_migrations
from infrahub.dependencies.registry import get_component_registry
from infrahub.events.branch_action import BranchCreatedEvent, BranchDeletedEvent, BranchMergedEvent, BranchRebasedEvent
from infrahub.events.models import EventMeta, InfrahubEvent
from infrahub.events.node_action import get_node_event
from infrahub.exceptions import BranchNotFoundError, MergeFailedError, ValidationError
from infrahub.graphql.mutations.models import BranchCreateModel  # noqa: TC001
from infrahub.log import get_log_data
from infrahub.message_bus import Meta, messages
from infrahub.services import InfrahubServices  # noqa: TC001  needed for prefect flow
from infrahub.worker import WORKER_IDENTITY
from infrahub.workflows.catalogue import (
    BRANCH_CANCEL_PROPOSED_CHANGES,
    DIFF_REFRESH_ALL,
    GIT_REPOSITORIES_CREATE_BRANCH,
    IPAM_RECONCILIATION,
)
from infrahub.workflows.utils import add_tags


@flow(name="branch-rebase", flow_run_name="Rebase branch {branch}")
async def rebase_branch(branch: str, context: InfrahubContext, service: InfrahubServices) -> None:  # noqa: PLR0915
    async with service.database.start_session() as db:
        log = get_run_logger()
        await add_tags(branches=[branch])
        obj = await Branch.get_by_name(db=db, name=branch)
        base_branch = await Branch.get_by_name(db=db, name=registry.default_branch)
        component_registry = get_component_registry()
        diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=obj)
        diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=obj)
        diff_merger = await component_registry.get_component(DiffMerger, db=db, branch=obj)
        initial_from_time = Timestamp(obj.get_branched_from())
        merger = BranchMerger(
            db=db,
            diff_coordinator=diff_coordinator,
            diff_merger=diff_merger,
            diff_repository=diff_repository,
            source_branch=obj,
            service=service,
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
                message=SchemaValidateMigrationData(
                    branch=obj, schema_branch=candidate_schema, constraints=constraints
                ),
                service=service,
            )
            error_messages = [violation.message for response in responses for violation in response.violations]
            if error_messages:
                raise ValidationError(",\n".join(error_messages))

        schema_in_main_before = merger.destination_schema.duplicate()
        migrations = []
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
                    ),
                    service=service,
                )
                for error in errors:
                    log.error(error)

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
            await service.workflow.submit_workflow(
                workflow=IPAM_RECONCILIATION,
                context=context,
                parameters={"branch": obj.name, "ipam_node_details": ipam_node_details},
            )

    await service.workflow.submit_workflow(
        workflow=DIFF_REFRESH_ALL, context=context, parameters={"branch_name": obj.name}
    )

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

    for event in events:
        await service.event.send(event)


@flow(name="branch-merge", flow_run_name="Merge branch {branch} into main")
async def merge_branch(
    branch: str, context: InfrahubContext, service: InfrahubServices, proposed_change_id: str | None = None
) -> None:
    async with service.database.start_session() as db:
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
                branch_diff = await merger.merge()
            except Exception as exc:
                log.exception("Merge failed, beginning rollback")
                await merger.rollback()
                raise MergeFailedError(branch_name=branch) from exc
            await merger.update_schema()

        changelog_collector = DiffChangelogCollector(diff=branch_diff, branch=obj, db=db)
        node_events = changelog_collector.collect_changelogs()
        if merger and merger.migrations:
            errors = await schema_apply_migrations(
                message=SchemaApplyMigrationData(
                    branch=merger.destination_branch,
                    new_schema=merger.destination_schema,
                    previous_schema=merger.initial_source_schema,
                    migrations=merger.migrations,
                ),
                service=service,
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
                context=context,
                parameters={"branch": registry.default_branch, "ipam_node_details": ipam_node_details},
            )
        # -------------------------------------------------------------
        # remove tracking ID from the diff because there is no diff after the merge
        # -------------------------------------------------------------
        diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=obj)
        await diff_repository.mark_tracking_ids_merged(tracking_ids=[BranchTrackingId(name=obj.name)])

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
            context=context,
            meta=Meta(initiator_id=WORKER_IDENTITY, request_id=request_id),
        )
        await service.message_bus.send(message=message)

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

        for event in events:
            await service.event.send(event=event)


@flow(name="branch-delete", flow_run_name="Delete branch {branch}")
async def delete_branch(branch: str, context: InfrahubContext, service: InfrahubServices) -> None:
    await add_tags(branches=[branch])

    async with service.database.start_session() as db:
        obj = await Branch.get_by_name(db=db, name=str(branch))
        await obj.delete(db=db)

        event = BranchDeletedEvent(
            branch_name=branch,
            branch_id=str(obj.uuid),
            sync_with_git=obj.sync_with_git,
            meta=EventMeta.from_context(context=context, branch=registry.get_global_branch()),
        )

        await service.workflow.submit_workflow(
            workflow=BRANCH_CANCEL_PROPOSED_CHANGES, context=context, parameters={"branch_name": branch}
        )

        await service.event.send(event=event)


@flow(
    name="branch-validate",
    flow_run_name="Validate branch {branch} for conflicts",
    description="Validate if the branch has some conflicts",
    persist_result=True,
)
async def validate_branch(branch: str, service: InfrahubServices) -> State:
    await add_tags(branches=[branch])

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
async def create_branch(model: BranchCreateModel, context: InfrahubContext, service: InfrahubServices) -> None:
    await add_tags(branches=[model.name])

    async with service.database.start_session() as db:
        try:
            await Branch.get_by_name(db=db, name=model.name)
            raise ValueError(f"The branch {model.name}, already exist")
        except BranchNotFoundError:
            pass

        data_dict: dict[str, Any] = dict(model)
        data_dict.pop("is_isolated", None)

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

        event = BranchCreatedEvent(
            branch_name=obj.name,
            branch_id=str(obj.uuid),
            sync_with_git=obj.sync_with_git,
            meta=EventMeta.from_context(context=context, branch=registry.get_global_branch()),
        )
        await service.event.send(event=event)

        if obj.sync_with_git:
            await service.workflow.submit_workflow(
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
