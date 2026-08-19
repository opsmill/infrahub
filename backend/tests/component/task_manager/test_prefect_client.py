from collections.abc import AsyncGenerator, Generator

import pytest
from prefect import flow
from prefect.client.orchestration import PrefectClient, get_client
from prefect.client.schemas.filters import ArtifactFilter, ArtifactFilterKey, FlowRunFilter, FlowRunFilterId
from prefect.client.schemas.objects import State, StateType

from infrahub.task_manager.flow_run.constants import WEBHOOK_HTTP_ARTIFACT_KEY, WEBHOOK_HTTP_ARTIFACT_TYPE
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


async def test_cancellation_requested_sees_an_overwritten_cancellation(prefect_client: PrefectClient) -> None:
    adapter = PrefectClientAdapter(prefect_client)
    run = await prefect_client.create_flow_run(flow=_noop_flow, state=State(type=StateType.SCHEDULED))

    await adapter.set_flow_run_state(flow_run_id=run.id, state=State(type=StateType.CANCELLING), force=False)
    # A retry resuming overwrites the current state; the recorded request must still be seen.
    await adapter.set_flow_run_state(flow_run_id=run.id, state=State(type=StateType.RUNNING), force=True)

    assert await adapter.cancellation_requested(flow_run_id=run.id) is True


async def test_cancellation_requested_is_false_without_a_request(prefect_client: PrefectClient) -> None:
    adapter = PrefectClientAdapter(prefect_client)
    run = await prefect_client.create_flow_run(flow=_noop_flow, state=State(type=StateType.SCHEDULED))

    assert await adapter.cancellation_requested(flow_run_id=run.id) is False


async def test_create_artifact_attaches_a_readable_artifact_to_the_run(prefect_client: PrefectClient) -> None:
    adapter = PrefectClientAdapter(prefect_client)
    run = await prefect_client.create_flow_run(flow=_noop_flow, state=State(type=StateType.COMPLETED))
    data = {"request": {"url": "http://target/hook"}, "response": None, "error": None}

    await adapter.create_artifact(
        key=WEBHOOK_HTTP_ARTIFACT_KEY, artifact_type=WEBHOOK_HTTP_ARTIFACT_TYPE, data=data, flow_run_id=run.id
    )

    artifacts = await adapter.read_artifacts(
        artifact_filter=ArtifactFilter(key=ArtifactFilterKey(any_=[WEBHOOK_HTTP_ARTIFACT_KEY])),
        flow_run_filter=FlowRunFilter(id=FlowRunFilterId(any_=[run.id])),
    )

    assert len(artifacts) == 1
    assert artifacts[0].data == data
