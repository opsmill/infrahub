from dataclasses import dataclass

import pytest

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.events.models import EventBranchContext, EventContext
from infrahub.services.adapters.workflow import prepare_dispatch, resolve_priority
from infrahub.workflows.constants import WorkflowPriority
from infrahub.workflows.models import WorkflowDefinition


def build_workflow(default_priority: WorkflowPriority = WorkflowPriority.MEDIUM) -> WorkflowDefinition:
    return WorkflowDefinition(
        name="test-workflow",
        module="tests.fixtures",
        function="a_flow",
        default_priority=default_priority,
    )


def build_context(priority: WorkflowPriority | None = None) -> InfrahubContext:
    return InfrahubContext(
        branch=BranchContext(name="main", id="1111aaaa-0000-0000-0000-000000000000"),
        account=AccountSession(auth_type=AuthType.JWT, authenticated=True, account_id="account-a"),
        priority=priority,
    )


def build_event_context() -> EventContext:
    return EventContext(branch=EventBranchContext(name="main"), account_id="account-a")


@dataclass
class ResolutionCase:
    name: str
    priority: WorkflowPriority | None
    context: InfrahubContext | EventContext | None
    default_priority: WorkflowPriority
    expected: WorkflowPriority


RESOLUTION_CASES = [
    ResolutionCase(
        name="explicit_wins_without_context",
        priority=WorkflowPriority.HIGH,
        context=None,
        default_priority=WorkflowPriority.MEDIUM,
        expected=WorkflowPriority.HIGH,
    ),
    ResolutionCase(
        name="explicit_wins_over_event_context",
        priority=WorkflowPriority.HIGH,
        context=build_event_context(),
        default_priority=WorkflowPriority.MEDIUM,
        expected=WorkflowPriority.HIGH,
    ),
    ResolutionCase(
        name="explicit_wins_over_context_without_priority",
        priority=WorkflowPriority.HIGH,
        context=build_context(priority=None),
        default_priority=WorkflowPriority.MEDIUM,
        expected=WorkflowPriority.HIGH,
    ),
    ResolutionCase(
        name="explicit_wins_over_context_priority",
        priority=WorkflowPriority.HIGH,
        context=build_context(priority=WorkflowPriority.LOW),
        default_priority=WorkflowPriority.MEDIUM,
        expected=WorkflowPriority.HIGH,
    ),
    ResolutionCase(
        name="context_priority_wins_over_catalogue_default",
        priority=None,
        context=build_context(priority=WorkflowPriority.HIGH),
        default_priority=WorkflowPriority.MEDIUM,
        expected=WorkflowPriority.HIGH,
    ),
    ResolutionCase(
        name="low_context_priority_not_floored_by_high_catalogue_default",
        priority=None,
        context=build_context(priority=WorkflowPriority.LOW),
        default_priority=WorkflowPriority.HIGH,
        expected=WorkflowPriority.LOW,
    ),
    ResolutionCase(
        name="catalogue_default_without_context",
        priority=None,
        context=None,
        default_priority=WorkflowPriority.LOW,
        expected=WorkflowPriority.LOW,
    ),
    ResolutionCase(
        name="catalogue_default_with_event_context",
        priority=None,
        context=build_event_context(),
        default_priority=WorkflowPriority.LOW,
        expected=WorkflowPriority.LOW,
    ),
    ResolutionCase(
        name="catalogue_default_with_context_without_priority",
        priority=None,
        context=build_context(priority=None),
        default_priority=WorkflowPriority.LOW,
        expected=WorkflowPriority.LOW,
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(test_case, id=test_case.name) for test_case in RESOLUTION_CASES])
def test_resolve_priority(test_case: ResolutionCase) -> None:
    workflow = build_workflow(default_priority=test_case.default_priority)

    resolved = resolve_priority(priority=test_case.priority, context=test_case.context, workflow=workflow)

    assert resolved is test_case.expected


class TestPrepareDispatch:
    def test_explicit_priority_stamps_copy_and_routes(self) -> None:
        caller_context = build_context(priority=None)

        dispatched_context, work_queue_name = prepare_dispatch(
            workflow=build_workflow(), context=caller_context, priority=WorkflowPriority.HIGH
        )

        assert isinstance(dispatched_context, InfrahubContext)
        assert dispatched_context is not caller_context
        assert dispatched_context.priority is WorkflowPriority.HIGH
        assert caller_context.priority is None
        assert work_queue_name == WorkflowPriority.HIGH.queue_name

    def test_explicit_priority_overrides_context_priority(self) -> None:
        caller_context = build_context(priority=WorkflowPriority.LOW)

        dispatched_context, work_queue_name = prepare_dispatch(
            workflow=build_workflow(), context=caller_context, priority=WorkflowPriority.HIGH
        )

        assert isinstance(dispatched_context, InfrahubContext)
        assert dispatched_context.priority is WorkflowPriority.HIGH
        assert caller_context.priority is WorkflowPriority.LOW
        assert work_queue_name == WorkflowPriority.HIGH.queue_name

    def test_context_priority_stamps_and_routes(self) -> None:
        caller_context = build_context(priority=WorkflowPriority.LOW)

        dispatched_context, work_queue_name = prepare_dispatch(
            workflow=build_workflow(default_priority=WorkflowPriority.HIGH), context=caller_context, priority=None
        )

        assert isinstance(dispatched_context, InfrahubContext)
        assert dispatched_context is not caller_context
        assert dispatched_context.priority is WorkflowPriority.LOW
        assert work_queue_name == WorkflowPriority.LOW.queue_name

    def test_catalogue_default_stamps_but_does_not_route(self) -> None:
        caller_context = build_context(priority=None)

        dispatched_context, work_queue_name = prepare_dispatch(
            workflow=build_workflow(default_priority=WorkflowPriority.MEDIUM), context=caller_context, priority=None
        )

        assert isinstance(dispatched_context, InfrahubContext)
        assert dispatched_context is not caller_context
        assert dispatched_context.priority is WorkflowPriority.MEDIUM
        assert caller_context.priority is None
        assert work_queue_name is None

    def test_catalogue_default_stamp_outranks_next_hop_catalogue_default(self) -> None:
        root_context = build_context(priority=None)

        stamped_context, _ = prepare_dispatch(
            workflow=build_workflow(default_priority=WorkflowPriority.MEDIUM), context=root_context, priority=None
        )
        dispatched_context, work_queue_name = prepare_dispatch(
            workflow=build_workflow(default_priority=WorkflowPriority.HIGH), context=stamped_context, priority=None
        )

        assert isinstance(dispatched_context, InfrahubContext)
        assert dispatched_context.priority is WorkflowPriority.MEDIUM
        assert work_queue_name == WorkflowPriority.MEDIUM.queue_name

    def test_event_context_passes_through_unstamped(self) -> None:
        caller_context = build_event_context()

        dispatched_context, work_queue_name = prepare_dispatch(
            workflow=build_workflow(), context=caller_context, priority=None
        )

        assert dispatched_context is caller_context
        assert work_queue_name is None

    def test_event_context_with_explicit_priority_routes_without_stamping(self) -> None:
        caller_context = build_event_context()

        dispatched_context, work_queue_name = prepare_dispatch(
            workflow=build_workflow(), context=caller_context, priority=WorkflowPriority.LOW
        )

        assert dispatched_context is caller_context
        assert work_queue_name == WorkflowPriority.LOW.queue_name

    def test_no_context_no_priority_routes_nothing(self) -> None:
        dispatched_context, work_queue_name = prepare_dispatch(workflow=build_workflow(), context=None, priority=None)

        assert dispatched_context is None
        assert work_queue_name is None

    def test_no_context_with_explicit_priority_routes(self) -> None:
        dispatched_context, work_queue_name = prepare_dispatch(
            workflow=build_workflow(), context=None, priority=WorkflowPriority.HIGH
        )

        assert dispatched_context is None
        assert work_queue_name == WorkflowPriority.HIGH.queue_name
