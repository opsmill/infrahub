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


class SubmissionWindow:
    """Hand out a worker's latest scheduled flow runs for submission, in poll order and a bounded number at a time."""

    def __init__(self, capacity: int, reservations: FlowRunReservations) -> None:
        self._capacity = capacity
        self._reservations = reservations
        self._candidates: deque[WorkerFlowRunResponse] = deque()
        self._in_flight: set[UUID] = set()
        self._finished_since_last_poll: set[UUID] = set()

    @property
    def in_flight(self) -> int:
        return len(self._in_flight)

    def replace_candidates(self, entries: list[WorkerFlowRunResponse]) -> None:
        """Use a new poll as the candidates, leaving out the runs this worker took since the previous poll."""
        # A poll read before this worker's claims landed still lists those runs, and since polls run one at a time
        # such a run is either still in flight or finished since the previous poll.
        taken = self._in_flight | self._finished_since_last_poll
        self._finished_since_last_poll = set()
        self._candidates = deque(entry for entry in entries if entry.flow_run.id not in taken)

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
            try:
                reserved = await self._reservations.reserve(flow_run_id=flow_run_id)
            except BaseException:
                # The caller never receives this batch, so nothing else frees its slots; its reservations expire.
                self._in_flight.difference_update([flow_run_id, *(taken_entry.flow_run.id for taken_entry in taken)])
                raise
            if not reserved:
                self._in_flight.discard(flow_run_id)
                continue
            taken.append(entry)
        return taken

    def complete(self, flow_run_id: UUID) -> None:
        """Free the slot of a run whose submission finished and leave the run out of the next poll.

        Its reservation is left to expire so that another worker holding an older poll does not claim it again.
        """
        self._in_flight.discard(flow_run_id)
        self._finished_since_last_poll.add(flow_run_id)

    def abandon(self, flow_run_ids: list[UUID]) -> None:
        """Free the slots of taken runs that were never submitted, leaving their reservations to expire."""
        self._in_flight.difference_update(flow_run_ids)

    async def return_unsubmitted(self, flow_run_ids: list[UUID]) -> None:
        """Free the slots and the reservations of taken runs that were not submitted."""
        # Every slot is freed before the first release so that a failed release cannot keep a slot taken.
        self._in_flight.difference_update(flow_run_ids)
        for flow_run_id in flow_run_ids:
            await self._reservations.release(flow_run_id=flow_run_id)
