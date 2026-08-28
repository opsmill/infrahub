from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import InfrahubContext
from infrahub.core.initialization import create_branch
from infrahub.core.merge.post_merge import PostMergeDispatcher
from infrahub.core.merge.recompute_coalescing import DisabledPythonTargetDeriver
from infrahub.core.merge.repository_merge_dispatcher import RepositoryMergeDispatcher
from infrahub.core.registry import registry
from infrahub.events.branch_action import BranchMergedEvent
from infrahub.events.schema_action import SchemaUpdatedEvent
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from tests.adapters.event import FailingKindInfrahubEvent, MemoryInfrahubEvent
from tests.adapters.python_target_sources import RecordingPythonTargetDeriver

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.merge.recompute_coalescing import PythonTargetDeriver
    from infrahub.core.models import SchemaDiff
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


def _build_dispatcher(
    db: InfrahubDatabase,
    source_branch: Branch,
    destination_branch: Branch,
    event_service: MemoryInfrahubEvent,
    python_deriver: PythonTargetDeriver,
) -> PostMergeDispatcher:
    workflow = WorkflowLocalExecution()
    return PostMergeDispatcher(
        repository_merge_dispatcher=RepositoryMergeDispatcher(
            db=db, source_branch=source_branch, destination_branch=destination_branch, workflow=workflow
        ),
        workflow=workflow,
        event_service=event_service,
        default_branch=destination_branch,
        python_deriver=python_deriver,
    )


def _derived_value_schema_diff(default_branch: Branch) -> tuple[SchemaDiff, str]:
    """A schema change confined to a derived-value definition, with the candidate's hash."""
    base_schema = registry.schema.get_schema_branch(name=default_branch.name)
    candidate = base_schema.duplicate()
    car = candidate.get(name="TestCar", duplicate=True)
    car.display_labels = ["nbr_seats__value"]
    candidate.set(name="TestCar", schema=car)
    candidate.process()
    return base_schema.diff(other=candidate), candidate.get_hash()


def _context(default_branch: Branch) -> InfrahubContext:
    return InfrahubContext.init(
        branch=default_branch,
        account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
    )


class TestPostMergeSchemaEvent:
    """A merge that applied schema changes emits a scoped SchemaUpdatedEvent for the destination branch.

    The event drives the display-label, HFID and computed-attribute backfills so destination-only nodes
    refresh their derived values; its changed_elements scope keeps that recompute limited to the schema
    elements the merge actually changed.
    """

    async def test_emits_scoped_schema_updated_event_when_schema_changed(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        car_person_schema: SchemaBranch,
    ) -> None:
        source_branch = await create_branch(branch_name="feature", db=db)
        memory_event = MemoryInfrahubEvent()
        dispatcher = _build_dispatcher(db, source_branch, default_branch, memory_event, DisabledPythonTargetDeriver())

        schema_diff, schema_hash = _derived_value_schema_diff(default_branch)

        await dispatcher.dispatch_events(
            branch=source_branch,
            proposed_change_id=None,
            node_events=[],
            context=_context(default_branch),
            schema_diff=schema_diff,
            schema_hash=schema_hash,
        )

        schema_events = [event for event in memory_event.events if isinstance(event, SchemaUpdatedEvent)]
        assert len(schema_events) == 1
        event = schema_events[0]
        assert event.branch_name == default_branch.name
        assert event.schema_hash == schema_hash
        assert event.changed_elements is not None
        assert "display_labels" in event.changed_elements.changed_fields.get("TestCar", [])

    async def test_no_schema_updated_event_when_no_schema_change(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        car_person_schema: SchemaBranch,
    ) -> None:
        source_branch = await create_branch(branch_name="feature", db=db)
        memory_event = MemoryInfrahubEvent()
        dispatcher = _build_dispatcher(db, source_branch, default_branch, memory_event, DisabledPythonTargetDeriver())

        await dispatcher.dispatch_events(
            branch=source_branch,
            proposed_change_id=None,
            node_events=[],
            context=_context(default_branch),
            schema_diff=None,
        )

        assert not [event for event in memory_event.events if isinstance(event, SchemaUpdatedEvent)]
        assert [event for event in memory_event.events if isinstance(event, BranchMergedEvent)]

    async def test_a_schema_event_that_went_out_scopes_the_coalesced_pass(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        car_person_schema: SchemaBranch,
    ) -> None:
        """The pass drops the pairs this backfill covers, so it has to be told what changed."""
        source_branch = await create_branch(branch_name="feature", db=db)
        deriver = RecordingPythonTargetDeriver(targets=[])
        dispatcher = _build_dispatcher(db, source_branch, default_branch, MemoryInfrahubEvent(), deriver)
        schema_diff, schema_hash = _derived_value_schema_diff(default_branch)

        await dispatcher.dispatch_events(
            branch=source_branch,
            proposed_change_id=None,
            node_events=[],
            context=_context(default_branch),
            schema_diff=schema_diff,
            schema_hash=schema_hash,
        )

        assert len(deriver.calls) == 1
        _, _, scope = deriver.calls[0]
        assert scope is not None
        assert "display_labels" in scope.changed_fields.get("TestCar", frozenset())

    async def test_a_failed_schema_event_leaves_the_coalesced_pass_unscoped(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        car_person_schema: SchemaBranch,
    ) -> None:
        """A backfill whose event never went out covers nothing, so the pass must drop nothing.

        The send failure is absorbed so it cannot abort the remaining events, which is exactly why
        the scope cannot be handed over before the send.
        """
        source_branch = await create_branch(branch_name="feature", db=db)
        deriver = RecordingPythonTargetDeriver(targets=[])
        event_service = FailingKindInfrahubEvent(failing_kind=SchemaUpdatedEvent)
        dispatcher = _build_dispatcher(db, source_branch, default_branch, event_service, deriver)
        schema_diff, schema_hash = _derived_value_schema_diff(default_branch)

        await dispatcher.dispatch_events(
            branch=source_branch,
            proposed_change_id=None,
            node_events=[],
            context=_context(default_branch),
            schema_diff=schema_diff,
            schema_hash=schema_hash,
        )

        # The merge event still went out, so the failure was absorbed rather than aborting the rest.
        assert [type(event).__name__ for event in event_service.events] == ["BranchMergedEvent"]
        assert deriver.calls == [(default_branch.name, (), None)]


class TestPostMergeBranchMergedEvent:
    """The branch-merged event is scoped to the default branch for webhook matching.

    Webhook branch scoping matches the event's `infrahub.branch` related-resource label, so a
    Default-Branch scoped webhook fires for a merge only when that label is the default branch. The
    event payload still identifies the branch that was merged.
    """

    async def test_branch_merged_event_scoped_to_default_branch(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        car_person_schema: SchemaBranch,
    ) -> None:
        source_branch = await create_branch(branch_name="feature", db=db)
        memory_event = MemoryInfrahubEvent()
        dispatcher = _build_dispatcher(db, source_branch, default_branch, memory_event, DisabledPythonTargetDeriver())

        await dispatcher.dispatch_events(
            branch=source_branch,
            proposed_change_id=None,
            node_events=[],
            context=_context(source_branch),
            schema_diff=None,
        )

        merged_events = [event for event in memory_event.events if isinstance(event, BranchMergedEvent)]
        assert len(merged_events) == 1
        event = merged_events[0]

        # Payload identity keeps naming the branch that was merged.
        assert event.branch_name == source_branch.name
        assert event.branch_id == str(source_branch.get_uuid())

        # The webhook scoping branch is the default branch, not the global branch.
        branch_related = [
            entry for entry in event.get_related() if entry.get("prefect.resource.role") == "infrahub.branch"
        ]
        assert len(branch_related) == 1
        assert branch_related[0]["infrahub.resource.label"] == default_branch.name
