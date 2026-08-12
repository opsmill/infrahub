from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import InfrahubContext
from infrahub.core.initialization import create_branch
from infrahub.core.merge.post_merge import PostMergeDispatcher
from infrahub.core.merge.python_target_resolution import DroppingPythonTargetResolver
from infrahub.core.merge.repository_merge_dispatcher import RepositoryMergeDispatcher
from infrahub.core.registry import registry
from infrahub.events.branch_action import BranchMergedEvent
from infrahub.events.schema_action import SchemaUpdatedEvent
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from tests.adapters.event import MemoryInfrahubEvent

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


class TestPostMergeSchemaEvent:
    """A merge that applied schema changes emits a scoped SchemaUpdatedEvent for the destination branch.

    The event drives the display-label, HFID and computed-attribute backfills so destination-only nodes
    refresh their derived values; its changed_elements scope keeps that recompute limited to the schema
    elements the merge actually changed.
    """

    def _build_dispatcher(
        self,
        db: InfrahubDatabase,
        source_branch: Branch,
        destination_branch: Branch,
        event_service: MemoryInfrahubEvent,
    ) -> PostMergeDispatcher:
        workflow = WorkflowLocalExecution()
        return PostMergeDispatcher(
            repository_merge_dispatcher=RepositoryMergeDispatcher(
                db=db, source_branch=source_branch, destination_branch=destination_branch, workflow=workflow
            ),
            workflow=workflow,
            event_service=event_service,
            default_branch=destination_branch,
            global_branch=registry.get_global_branch(),
            # This schema carries no Python computed attribute, so the family has nothing to resolve.
            python_target_resolver=DroppingPythonTargetResolver(),
        )

    def _context(self, default_branch: Branch) -> InfrahubContext:
        return InfrahubContext.init(
            branch=default_branch,
            account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
        )

    async def test_emits_scoped_schema_updated_event_when_schema_changed(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: SchemaBranch,
        car_person_schema: SchemaBranch,
    ) -> None:
        source_branch = await create_branch(branch_name="feature", db=db)
        memory_event = MemoryInfrahubEvent()
        dispatcher = self._build_dispatcher(db, source_branch, default_branch, memory_event)

        # A schema change confined to a derived-value definition on the destination branch.
        base_schema = registry.schema.get_schema_branch(name=default_branch.name)
        candidate = base_schema.duplicate()
        car = candidate.get(name="TestCar", duplicate=True)
        car.display_labels = ["nbr_seats__value"]
        candidate.set(name="TestCar", schema=car)
        candidate.process()
        schema_diff = base_schema.diff(other=candidate)

        await dispatcher.dispatch_events(
            branch=source_branch,
            proposed_change_id=None,
            node_events=[],
            context=self._context(default_branch),
            schema_diff=schema_diff,
            schema_hash=candidate.get_hash(),
        )

        schema_events = [event for event in memory_event.events if isinstance(event, SchemaUpdatedEvent)]
        assert len(schema_events) == 1
        event = schema_events[0]
        assert event.branch_name == default_branch.name
        assert event.schema_hash == candidate.get_hash()
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
        dispatcher = self._build_dispatcher(db, source_branch, default_branch, memory_event)

        await dispatcher.dispatch_events(
            branch=source_branch,
            proposed_change_id=None,
            node_events=[],
            context=self._context(default_branch),
            schema_diff=None,
        )

        assert not [event for event in memory_event.events if isinstance(event, SchemaUpdatedEvent)]
        assert [event for event in memory_event.events if isinstance(event, BranchMergedEvent)]
