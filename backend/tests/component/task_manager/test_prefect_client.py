from collections.abc import AsyncGenerator, Generator

import pytest
from prefect import flow
from prefect.client.orchestration import PrefectClient, get_client
from prefect.client.schemas.objects import State, StateType

from infrahub.task_manager.flow_run.prefect_client import PrefectClientAdapter


@flow
def _noop_flow() -> None:
    """A trivial flow used only to create flow runs whose state transitions can be driven."""


@pytest.fixture(scope="module")
async def prefect_client(prefect_test_fixture: Generator[None]) -> AsyncGenerator[PrefectClient, None]:
    async with get_client(sync_client=False) as client:
        yield client


async def test_set_flow_run_state_cancels_an_in_flight_run(prefect_client: PrefectClient) -> None:
    adapter = PrefectClientAdapter(prefect_client)
    run = await prefect_client.create_flow_run(flow=_noop_flow, state=State(type=StateType.SCHEDULED))

    resulting_state = await adapter.set_flow_run_state(
        flow_run_id=run.id, state=State(type=StateType.CANCELLING), force=False
    )

    assert resulting_state == StateType.CANCELLED


async def test_set_flow_run_state_leaves_a_settled_run_terminal(prefect_client: PrefectClient) -> None:
    adapter = PrefectClientAdapter(prefect_client)
    run = await prefect_client.create_flow_run(flow=_noop_flow, state=State(type=StateType.COMPLETED))

    resulting_state = await adapter.set_flow_run_state(
        flow_run_id=run.id, state=State(type=StateType.CANCELLING), force=False
    )

    assert resulting_state == StateType.COMPLETED
