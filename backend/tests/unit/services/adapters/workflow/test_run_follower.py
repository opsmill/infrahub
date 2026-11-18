import asyncio
from uuid import UUID, uuid4

import pytest
from prefect.client.schemas.filters import FlowRunFilter
from prefect.client.schemas.objects import FlowRun
from prefect.states import Completed

from infrahub.services.adapters.workflow.run_follower import READ_PAGE_SIZE, FlowRunFollower


class FinishingRunsReader:
    """Reports each followed run as final once it has been read `polls_until_final` times, and records every read."""

    def __init__(self, polls_until_final: int = 1) -> None:
        self.polls_until_final = polls_until_final
        self.reads: list[list[UUID]] = []
        self._times_read: dict[UUID, int] = {}

    async def read_flow_runs(
        self, *, flow_run_filter: FlowRunFilter | None = None, limit: int | None = None
    ) -> list[FlowRun]:
        assert flow_run_filter is not None
        assert flow_run_filter.id is not None
        ids = list(flow_run_filter.id.any_ or [])
        assert limit is not None
        assert len(ids) <= limit
        self.reads.append(ids)
        final_runs = []
        for flow_run_id in ids:
            self._times_read[flow_run_id] = self._times_read.get(flow_run_id, 0) + 1
            if self._times_read[flow_run_id] >= self.polls_until_final:
                final_runs.append(FlowRun(id=flow_run_id, flow_id=uuid4(), state=Completed()))
        return final_runs


class UnreachableReader:
    async def read_flow_runs(
        self, *, flow_run_filter: FlowRunFilter | None = None, limit: int | None = None
    ) -> list[FlowRun]:
        raise ConnectionError("task manager unreachable")


async def test_each_poll_reads_all_followed_runs_in_pages() -> None:
    reader = FinishingRunsReader(polls_until_final=2)
    follower = FlowRunFollower(client=reader, poll_interval=0)
    flow_run_ids = [uuid4() for _ in range(2 * READ_PAGE_SIZE + 50)]

    flow_runs = await asyncio.gather(*(follower.wait(flow_run_id=flow_run_id) for flow_run_id in flow_run_ids))

    assert [flow_run.id for flow_run in flow_runs] == flow_run_ids
    assert [len(ids) for ids in reader.reads] == [READ_PAGE_SIZE, READ_PAGE_SIZE, 50] * 2


async def test_a_read_error_fails_every_followed_run() -> None:
    follower = FlowRunFollower(client=UnreachableReader(), poll_interval=0)

    results = await asyncio.gather(
        *(follower.wait(flow_run_id=uuid4()) for _ in range(3)),
        return_exceptions=True,
    )

    assert all(isinstance(result, ConnectionError) for result in results)


async def test_a_run_followed_after_the_previous_ones_ended_is_still_followed() -> None:
    follower = FlowRunFollower(client=FinishingRunsReader(), poll_interval=0)
    first, second = uuid4(), uuid4()

    assert (await follower.wait(flow_run_id=first)).id == first
    assert (await asyncio.wait_for(follower.wait(flow_run_id=second), timeout=5)).id == second


async def test_a_cancelled_wait_stops_being_followed() -> None:
    reader = FinishingRunsReader(polls_until_final=1_000_000)
    follower = FlowRunFollower(client=reader, poll_interval=0)
    wait = asyncio.create_task(follower.wait(flow_run_id=uuid4()))
    await asyncio.sleep(0.01)

    wait.cancel()
    with pytest.raises(asyncio.CancelledError):
        await wait
    reads_after_cancel = len(reader.reads)
    await asyncio.sleep(0.01)

    assert len(reader.reads) <= reads_after_cancel + 1
