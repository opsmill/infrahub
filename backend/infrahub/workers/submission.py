from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from uuid import UUID

    from prefect.client.schemas.responses import WorkerFlowRunResponse


class FlowRunReservations(Protocol):
    """Keeps concurrent workers from claiming the same scheduled flow run."""

    async def reserve(self, flow_run_id: UUID) -> bool: ...

    async def release(self, flow_run_id: UUID) -> None: ...


class UnreservedFlowRuns:
    """Reservations that always succeed, leaving the server to reject a run claimed by another worker."""

    async def reserve(self, flow_run_id: UUID) -> bool:  # noqa: ARG002
        return True

    async def release(self, flow_run_id: UUID) -> None: ...


class SubmissionWindow:
    """Hand out a worker's latest scheduled flow runs for submission, in poll order and a bounded number at a time.

    The poll returns runs ordered by work queue priority, so keeping only the latest poll and
    submitting from its head lets a higher-priority run overtake everything still waiting.
    """

    def __init__(self, capacity: int, reservations: FlowRunReservations) -> None:
        self._capacity = capacity
        self._reservations = reservations
        self._candidates: deque[WorkerFlowRunResponse] = deque()
        self._in_flight: set[UUID] = set()

    @property
    def in_flight(self) -> int:
        return len(self._in_flight)

    def replace_candidates(self, entries: list[WorkerFlowRunResponse]) -> None:
        self._candidates = deque(entries)

    async def take(self) -> list[WorkerFlowRunResponse]:
        """Reserve candidates from the head of the latest poll until the window is full."""
        taken: list[WorkerFlowRunResponse] = []
        while self._candidates and len(self._in_flight) < self._capacity:
            entry = self._candidates.popleft()
            flow_run_id = entry.flow_run.id
            if flow_run_id in self._in_flight:
                continue
            # Hold the slot across the reservation await so that a concurrent take cannot overfill the window.
            self._in_flight.add(flow_run_id)
            reserved = False
            try:
                reserved = await self._reservations.reserve(flow_run_id=flow_run_id)
            finally:
                if not reserved:
                    self._in_flight.discard(flow_run_id)
            if reserved:
                taken.append(entry)
        return taken

    def complete(self, flow_run_id: UUID) -> None:
        """Free the slot of a run whose submission finished.

        The reservation is left to expire so that a worker still holding an older poll does not claim the run again.
        """
        self._in_flight.discard(flow_run_id)

    async def return_unsubmitted(self, flow_run_id: UUID) -> None:
        """Free the slot and the reservation of a taken run that was not submitted."""
        self._in_flight.discard(flow_run_id)
        await self._reservations.release(flow_run_id=flow_run_id)
