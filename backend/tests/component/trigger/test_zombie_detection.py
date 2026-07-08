from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from prefect import flow
from prefect.automations import AutomationCore
from prefect.client.schemas.objects import State, StateType
from prefect.events.clients import get_events_client
from prefect.events.schemas.events import Event

from infrahub.trigger.system import TRIGGER_CRASH_ZOMBIE_FLOWS

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from prefect.client.orchestration import PrefectClient

    from infrahub.trigger.models import SystemTriggerDefinition

# The shipped window outlasts the longest configured backoff; the event-driven tests scale it
# down so a verdict arrives within seconds instead of minutes.
SCALED_WINDOW = timedelta(seconds=20)
VERDICT_TIMEOUT_SECONDS = 60.0
POLL_INTERVAL_SECONDS = 1.0


@flow(name="retrying-under-zombie-watch")
async def _always_failing() -> None:
    raise ValueError("the target is unavailable")


async def register_automation(prefect_client: PrefectClient, definition: SystemTriggerDefinition) -> UUID:
    automation = AutomationCore(
        name=f"{definition.generate_name()}-{uuid4()}",
        description=definition.get_description(),
        enabled=True,
        trigger=definition.trigger.get_prefect(),
        actions=[action.get_prefect() for action in definition.actions],
    )
    return await prefect_client.create_automation(automation=automation)


@pytest.fixture
async def scaled_zombie_automation(prefect_client: PrefectClient) -> AsyncGenerator[None, None]:
    """Register the shipped zombie automation with a test-sized window, then remove it."""
    scaled = TRIGGER_CRASH_ZOMBIE_FLOWS.model_copy(deep=True)
    scaled.trigger.within = SCALED_WINDOW
    automation_id = await register_automation(prefect_client, scaled)
    yield
    await prefect_client.delete_automation(automation_id=automation_id)


async def emit_flow_run_event(event_name: str, flow_run_id: UUID) -> None:
    async with get_events_client() as events_client:
        await events_client.emit(
            Event(
                event=event_name,
                occurred=datetime.now(UTC),
                resource={"prefect.resource.id": f"prefect.flow-run.{flow_run_id}"},
            )
        )


async def create_waiting_run(prefect_client: PrefectClient) -> UUID:
    """Create a flow run parked in its retry wait, as an engine leaves it between attempts."""
    run = await prefect_client.create_flow_run(
        flow=_always_failing, state=State(type=StateType.SCHEDULED, name="AwaitingRetry")
    )
    return run.id


async def wait_for_state(prefect_client: PrefectClient, flow_run_id: UUID, expected: StateType) -> bool:
    deadline = asyncio.get_running_loop().time() + VERDICT_TIMEOUT_SECONDS
    while asyncio.get_running_loop().time() < deadline:
        run = await prefect_client.read_flow_run(flow_run_id)
        if run.state is not None and run.state.type == expected:
            return True
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
    return False


async def test_wait_that_never_resumes_is_marked_crashed(
    prefect_client: PrefectClient, scaled_zombie_automation: None
) -> None:
    """A retry wait that never resumes is a dead process and must be declared crashed."""
    flow_run_id = await create_waiting_run(prefect_client)
    await emit_flow_run_event("prefect.flow-run.heartbeat", flow_run_id)
    await emit_flow_run_event("prefect.flow-run.AwaitingRetry", flow_run_id)

    assert await wait_for_state(prefect_client, flow_run_id, StateType.CRASHED), (
        "a retry wait that never resumed was not declared crashed"
    )


async def test_wait_transition_restarts_the_countdown(
    prefect_client: PrefectClient, scaled_zombie_automation: None
) -> None:
    """Entering a retry wait restarts the no-heartbeat countdown rather than expiring it.

    The heartbeat arms the countdown; half a window later the run enters its wait. Were the
    transition not an expected event, the countdown armed by the heartbeat would expire on
    schedule. It must instead run from the transition, so the run is still untouched shortly
    after the original expiry.
    """
    flow_run_id = await create_waiting_run(prefect_client)
    await emit_flow_run_event("prefect.flow-run.heartbeat", flow_run_id)
    await asyncio.sleep(SCALED_WINDOW.total_seconds() / 2)
    await emit_flow_run_event("prefect.flow-run.AwaitingRetry", flow_run_id)

    # Check between the heartbeat's expiry and the transition's: crashed here means the
    # transition did not restart the countdown.
    await asyncio.sleep(SCALED_WINDOW.total_seconds() * 0.65)
    run = await prefect_client.read_flow_run(flow_run_id)
    assert run.state is not None
    assert run.state.type == StateType.SCHEDULED
