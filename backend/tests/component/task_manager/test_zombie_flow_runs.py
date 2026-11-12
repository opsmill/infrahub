from __future__ import annotations

import asyncio
from datetime import UTC, timedelta
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
from infrahub.task_manager.flow_run.zombie import ZombieFlowRunReaper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator
    from uuid import UUID

    from prefect.client.orchestration import PrefectClient

POLL_INTERVAL_SECONDS = 0.5
# Short enough to wait out in a test; the reaper's checks do not depend on the window's length.
TEST_WINDOW = timedelta(seconds=5)


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


async def wait_for_stored_heartbeat(
    adapter: PrefectClientAdapter, flow_run_id: UUID, since: DateTime
) -> DateTime | None:
    deadline = asyncio.get_running_loop().time() + PREFECT_EVENT_WAIT_SECONDS
    while asyncio.get_running_loop().time() < deadline:
        heartbeats = await adapter.latest_heartbeats(flow_run_ids=[flow_run_id], since=since)
        if flow_run_id in heartbeats:
            return heartbeats[flow_run_id]
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
    return None


async def wait_until(moment: DateTime) -> None:
    await asyncio.sleep(max(0.0, (moment - DateTime.now(tz=UTC)).total_seconds()))


async def test_crashes_the_running_run_that_stopped_sending_heartbeats(prefect_client: PrefectClient) -> None:
    adapter = PrefectClientAdapter(prefect_client)
    reaper = ZombieFlowRunReaper(client=adapter, window=TEST_WINDOW)
    silent = await prefect_client.create_flow_run(flow=_watched_flow, state=State(type=StateType.RUNNING))
    alive = await prefect_client.create_flow_run(flow=_watched_flow, state=State(type=StateType.RUNNING))
    finished = await prefect_client.create_flow_run(flow=_watched_flow, state=State(type=StateType.COMPLETED))
    started = DateTime.now(tz=UTC)
    await emit_heartbeat(silent.id)
    silent_beat = await wait_for_stored_heartbeat(adapter, silent.id, since=started - TEST_WINDOW)
    assert silent_beat is not None

    # The clock cannot be injected into the server, so a full window really passes before the live run beats again.
    await wait_until(silent_beat + TEST_WINDOW + TEST_WINDOW / 5)
    beat_again = DateTime.now(tz=UTC)
    await emit_heartbeat(alive.id)
    alive_beat = await wait_for_stored_heartbeat(adapter, alive.id, since=beat_again - TEST_WINDOW / 5)
    assert alive_beat is not None

    # Prefect stores events up to a flush interval after they occur, which can exceed the test window.
    check = await reaper.crash_zombies(now=alive_beat)

    assert set(check.crashed) & {silent.id, alive.id, finished.id} == {silent.id}
    silent_state = (await prefect_client.read_flow_run(silent.id)).state
    alive_state = (await prefect_client.read_flow_run(alive.id)).state
    finished_state = (await prefect_client.read_flow_run(finished.id)).state
    assert silent_state is not None
    assert alive_state is not None
    assert finished_state is not None
    assert (silent_state.type, silent_state.message, alive_state.type, finished_state.type) == (
        StateType.CRASHED,
        "Flow run marked as crashed due to missing heartbeats.",
        StateType.RUNNING,
        StateType.COMPLETED,
    )
