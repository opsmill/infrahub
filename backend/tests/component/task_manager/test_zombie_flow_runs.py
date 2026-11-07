from __future__ import annotations

import asyncio
from datetime import UTC
from typing import TYPE_CHECKING

import pytest
from prefect import flow
from prefect.client.orchestration import get_client
from prefect.client.schemas.objects import State, StateType
from prefect.events.clients import get_events_client
from prefect.events.schemas.events import Event, Resource
from prefect.types import DateTime
from tests.helpers.constants import PREFECT_EVENT_WAIT_SECONDS

from infrahub.task_manager.flow_run.prefect_client import (
    FLOW_RUN_HEARTBEAT_EVENT,
    FLOW_RUN_RESOURCE_PREFIX,
    PrefectClientAdapter,
)
from infrahub.task_manager.flow_run.zombie import ZOMBIE_CRASH_MESSAGE, ZOMBIE_HEARTBEAT_WINDOW, ZombieFlowRunReaper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator
    from uuid import UUID

    from prefect.client.orchestration import PrefectClient

POLL_INTERVAL_SECONDS = 0.5


@flow
def _watched_flow() -> None:
    """A flow used only to create flow runs whose states the test drives."""


@pytest.fixture(scope="module")
async def prefect_client(prefect_test_fixture: Generator[None]) -> AsyncGenerator[PrefectClient, None]:
    async with get_client(sync_client=False) as client:
        yield client


async def emit_heartbeat(flow_run_id: UUID) -> None:
    async with get_events_client() as events_client:
        await events_client.emit(
            Event(
                event=FLOW_RUN_HEARTBEAT_EVENT,
                occurred=DateTime.now(tz=UTC),
                resource=Resource({"prefect.resource.id": f"{FLOW_RUN_RESOURCE_PREFIX}{flow_run_id}"}),
            )
        )


async def wait_for_stored_heartbeat(adapter: PrefectClientAdapter, flow_run_id: UUID, since: DateTime) -> bool:
    deadline = asyncio.get_running_loop().time() + PREFECT_EVENT_WAIT_SECONDS
    while asyncio.get_running_loop().time() < deadline:
        if flow_run_id in await adapter.flow_runs_with_heartbeat_since(flow_run_ids=[flow_run_id], since=since):
            return True
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
    return False


async def test_crashes_a_silent_running_run_and_leaves_the_others(prefect_client: PrefectClient) -> None:
    adapter = PrefectClientAdapter(prefect_client)
    silent = await prefect_client.create_flow_run(flow=_watched_flow, state=State(type=StateType.RUNNING))
    alive = await prefect_client.create_flow_run(flow=_watched_flow, state=State(type=StateType.RUNNING))
    finished = await prefect_client.create_flow_run(flow=_watched_flow, state=State(type=StateType.COMPLETED))
    assert silent.state is not None
    assert alive.state is not None
    # Judged one window after both runs entered their running state, so both are old enough to be judged and a
    # heartbeat sent now falls inside the window.
    entered_running = max(silent.state.timestamp, alive.state.timestamp)
    judged_at = DateTime.fromtimestamp(entered_running.timestamp(), tz=UTC) + ZOMBIE_HEARTBEAT_WINDOW
    await emit_heartbeat(alive.id)
    assert await wait_for_stored_heartbeat(adapter, alive.id, since=judged_at - ZOMBIE_HEARTBEAT_WINDOW)

    crashed = await ZombieFlowRunReaper(client=adapter).crash_zombies(now=judged_at)

    assert silent.id in crashed
    assert alive.id not in crashed
    silent_after = await prefect_client.read_flow_run(silent.id)
    assert silent_after.state is not None
    assert (silent_after.state.type, silent_after.state.message) == (StateType.CRASHED, ZOMBIE_CRASH_MESSAGE)
    alive_after = await prefect_client.read_flow_run(alive.id)
    assert alive_after.state is not None
    assert alive_after.state.type == StateType.RUNNING
    finished_after = await prefect_client.read_flow_run(finished.id)
    assert finished_after.state is not None
    assert finished_after.state.type == StateType.COMPLETED
