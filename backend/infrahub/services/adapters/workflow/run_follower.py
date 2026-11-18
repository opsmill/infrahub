from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Protocol

from prefect.client.schemas.filters import (
    FlowRunFilter,
    FlowRunFilterId,
    FlowRunFilterState,
    FlowRunFilterStateType,
)
from prefect.client.schemas.objects import StateType

if TYPE_CHECKING:
    from uuid import UUID

    from prefect.client.schemas.objects import FlowRun

FINAL_STATE_TYPES = [StateType.COMPLETED, StateType.FAILED, StateType.CRASHED, StateType.CANCELLED]
# The Prefect API returns at most 200 flow runs per request.
READ_PAGE_SIZE = 200


class FlowRunReader(Protocol):
    """The part of the Prefect client the follower reads flow runs with."""

    async def read_flow_runs(
        self, *, flow_run_filter: FlowRunFilter | None = None, limit: int | None = None
    ) -> list[FlowRun]: ...


class FlowRunFollower:
    """Follow every flow run awaited through one Prefect client, reading them all at each poll in pages of 200."""

    def __init__(self, client: FlowRunReader, poll_interval: float) -> None:
        self._client = client
        self._poll_interval = poll_interval
        self._waiters: dict[UUID, asyncio.Future[FlowRun]] = {}
        self._poller: asyncio.Task[None] | None = None

    async def wait(self, flow_run_id: UUID) -> FlowRun:
        """Return the flow run once it reaches a final state.

        Raises:
            Exception: Whatever reading the flow runs raised, once the client has given up on its retries.

        """
        future: asyncio.Future[FlowRun] = asyncio.get_running_loop().create_future()
        self._waiters[flow_run_id] = future
        if self._poller is None or self._poller.done():
            self._poller = asyncio.create_task(self._poll())
        try:
            return await future
        finally:
            self._waiters.pop(flow_run_id, None)

    async def _poll(self) -> None:
        while self._waiters:
            await asyncio.sleep(self._poll_interval)
            try:
                final_runs = await self._read_final_runs(flow_run_ids=list(self._waiters))
            # Poller boundary: every waiter must receive the read failure, or it would wait forever.
            except Exception as exc:  # noqa: BLE001
                for future in self._waiters.values():
                    if not future.done():
                        future.set_exception(exc)
                return
            for flow_run in final_runs:
                waiter = self._waiters.get(flow_run.id)
                if waiter is not None and not waiter.done():
                    waiter.set_result(flow_run)

    async def _read_final_runs(self, flow_run_ids: list[UUID]) -> list[FlowRun]:
        final_runs: list[FlowRun] = []
        for start in range(0, len(flow_run_ids), READ_PAGE_SIZE):
            final_runs.extend(
                await self._client.read_flow_runs(
                    flow_run_filter=FlowRunFilter(
                        id=FlowRunFilterId(any_=flow_run_ids[start : start + READ_PAGE_SIZE]),
                        state=FlowRunFilterState(type=FlowRunFilterStateType(any_=FINAL_STATE_TYPES)),
                    ),
                    limit=READ_PAGE_SIZE,
                )
            )
        return final_runs
