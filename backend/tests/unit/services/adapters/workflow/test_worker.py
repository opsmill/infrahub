from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from prefect.client.schemas.objects import FlowRun, State, StateType

from infrahub.exceptions import ServiceUnavailableError
from infrahub.services.adapters.workflow.worker import FlowRunPickupChecker


def _flow_run(state: State | None) -> FlowRun:
    return FlowRun(flow_id=uuid.uuid4(), state=state)


@dataclass
class PickupCase:
    name: str
    state: State | None
    pickup_timeout: float | None


@pytest.mark.parametrize(
    "case",
    [
        PickupCase(name="scheduled_with_deadline", state=State(type=StateType.SCHEDULED), pickup_timeout=1.0),
        PickupCase(name="pending_with_deadline", state=State(type=StateType.PENDING), pickup_timeout=5.0),
    ],
    ids=lambda case: case.name,
)
def test_check_raises_when_run_not_picked_up(case: PickupCase) -> None:
    checker = FlowRunPickupChecker()

    with pytest.raises(
        ServiceUnavailableError,
        match=rf"was not picked up by a worker within {case.pickup_timeout} seconds",
    ):
        checker.check(
            response=_flow_run(case.state), workflow_full_name="dummy/flow", pickup_timeout=case.pickup_timeout
        )


@pytest.mark.parametrize(
    "case",
    [
        PickupCase(name="scheduled_without_deadline", state=State(type=StateType.SCHEDULED), pickup_timeout=None),
        PickupCase(name="pending_without_deadline", state=State(type=StateType.PENDING), pickup_timeout=None),
        PickupCase(name="completed_with_deadline", state=State(type=StateType.COMPLETED), pickup_timeout=1.0),
        PickupCase(name="running_with_deadline", state=State(type=StateType.RUNNING), pickup_timeout=1.0),
    ],
    ids=lambda case: case.name,
)
def test_check_returns_state_when_picked_up_or_no_deadline(case: PickupCase) -> None:
    checker = FlowRunPickupChecker()

    result = checker.check(
        response=_flow_run(case.state), workflow_full_name="dummy/flow", pickup_timeout=case.pickup_timeout
    )

    assert result is case.state


def test_check_raises_runtime_error_when_state_missing() -> None:
    checker = FlowRunPickupChecker()

    with pytest.raises(RuntimeError, match=r"Unable to read state from the response"):
        checker.check(response=_flow_run(None), workflow_full_name="dummy/flow", pickup_timeout=1.0)
