from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from prefect.client.schemas.objects import FlowRun
from prefect.client.schemas.responses import WorkerFlowRunResponse

from infrahub.workers.submission import SubmissionWindow
from tests.helpers.flow_run_reservations import UnreachableReservations


class RecordingReservations:
    """Reservations that refuse the runs held by another worker and record every release."""

    def __init__(self, held_elsewhere: set[UUID] | None = None) -> None:
        self.held_elsewhere = held_elsewhere or set()
        self.reserved: list[UUID] = []
        self.released: list[UUID] = []

    async def reserve(self, flow_run_id: UUID) -> bool:
        if flow_run_id in self.held_elsewhere:
            return False
        self.reserved.append(flow_run_id)
        return True

    async def release(self, flow_run_id: UUID) -> None:
        self.released.append(flow_run_id)


class ReservationsLostMidBatch(RecordingReservations):
    """Reservations that succeed for the first runs of a batch and then lose the cache."""

    def __init__(self, successes: int) -> None:
        super().__init__()
        self.successes = successes

    async def reserve(self, flow_run_id: UUID) -> bool:
        if len(self.reserved) == self.successes:
            raise ConnectionError("cache unreachable")
        return await super().reserve(flow_run_id=flow_run_id)


class UnreleasableReservations(RecordingReservations):
    """Reservations that succeed but whose cache is lost before they are given back."""

    async def release(self, flow_run_id: UUID) -> None:
        raise ConnectionError("cache unreachable")


def build_entries(count: int) -> list[WorkerFlowRunResponse]:
    return [
        WorkerFlowRunResponse(work_pool_id=uuid4(), work_queue_id=uuid4(), flow_run=FlowRun(flow_id=uuid4()))
        for _ in range(count)
    ]


def ids(entries: list[WorkerFlowRunResponse]) -> list[UUID]:
    return [entry.flow_run.id for entry in entries]


async def test_take_hands_out_the_poll_head_up_to_capacity() -> None:
    entries = build_entries(count=5)
    window = SubmissionWindow(capacity=3, reservations=RecordingReservations())
    window.replace_candidates(entries=entries)

    taken = await window.take()

    assert ids(taken) == ids(entries[:3])
    assert await window.take() == []


async def test_completed_submission_makes_room_for_the_next_candidate() -> None:
    entries = build_entries(count=4)
    window = SubmissionWindow(capacity=2, reservations=RecordingReservations())
    window.replace_candidates(entries=entries)
    await window.take()

    window.complete(flow_run_id=entries[0].flow_run.id)

    assert ids(await window.take()) == [entries[2].flow_run.id]


async def test_a_new_poll_replaces_the_candidates_of_the_previous_one() -> None:
    first_poll = build_entries(count=4)
    window = SubmissionWindow(capacity=1, reservations=RecordingReservations())
    window.replace_candidates(entries=first_poll)
    await window.take()
    window.complete(flow_run_id=first_poll[0].flow_run.id)

    high_priority = build_entries(count=1)
    window.replace_candidates(entries=high_priority + first_poll[1:])

    assert ids(await window.take()) == ids(high_priority)


async def test_run_still_in_flight_is_not_taken_again_from_a_later_poll() -> None:
    entries = build_entries(count=2)
    window = SubmissionWindow(capacity=2, reservations=RecordingReservations())
    window.replace_candidates(entries=entries[:1])
    await window.take()

    window.replace_candidates(entries=entries)

    assert ids(await window.take()) == [entries[1].flow_run.id]
    assert window.in_flight == 2


async def test_full_window_does_not_take_again_a_run_a_poll_listed_while_it_was_in_flight() -> None:
    entries = build_entries(count=3)
    window = SubmissionWindow(capacity=2, reservations=RecordingReservations())
    window.replace_candidates(entries=entries)
    await window.take()
    window.replace_candidates(entries=entries)

    window.complete(flow_run_id=entries[0].flow_run.id)

    assert ids(await window.take()) == [entries[2].flow_run.id]


async def test_run_that_finished_before_a_poll_still_listing_it_is_not_taken_again() -> None:
    entries = build_entries(count=2)
    window = SubmissionWindow(capacity=2, reservations=RecordingReservations())
    window.replace_candidates(entries=entries[:1])
    await window.take()
    window.complete(flow_run_id=entries[0].flow_run.id)

    window.replace_candidates(entries=entries)

    assert ids(await window.take()) == [entries[1].flow_run.id]


async def test_finished_run_is_left_out_of_the_next_poll_only() -> None:
    entries = build_entries(count=1)
    window = SubmissionWindow(capacity=1, reservations=RecordingReservations())
    window.replace_candidates(entries=entries)
    await window.take()
    window.complete(flow_run_id=entries[0].flow_run.id)
    window.replace_candidates(entries=entries)
    assert await window.take() == []

    window.replace_candidates(entries=entries)

    assert ids(await window.take()) == ids(entries)


async def test_abandoned_run_frees_its_slot_and_is_taken_again_from_the_next_poll() -> None:
    entries = build_entries(count=1)
    reservations = RecordingReservations()
    window = SubmissionWindow(capacity=1, reservations=reservations)
    window.replace_candidates(entries=entries)
    await window.take()

    window.abandon(flow_run_ids=ids(entries))

    assert window.in_flight == 0
    assert reservations.released == []
    window.replace_candidates(entries=entries)
    assert ids(await window.take()) == ids(entries)


async def test_run_reserved_by_another_worker_is_skipped_without_using_a_slot() -> None:
    entries = build_entries(count=3)
    reservations = RecordingReservations(held_elsewhere={entries[0].flow_run.id})
    window = SubmissionWindow(capacity=2, reservations=reservations)
    window.replace_candidates(entries=entries)

    taken = await window.take()

    assert ids(taken) == ids(entries[1:])
    assert window.in_flight == 2


async def test_unsubmitted_run_gives_back_its_slot_and_its_reservation() -> None:
    entries = build_entries(count=2)
    reservations = RecordingReservations()
    window = SubmissionWindow(capacity=1, reservations=reservations)
    window.replace_candidates(entries=entries)
    await window.take()

    await window.return_unsubmitted(flow_run_ids=[entries[0].flow_run.id])

    assert reservations.released == [entries[0].flow_run.id]
    assert ids(await window.take()) == [entries[1].flow_run.id]


async def test_completed_run_keeps_its_reservation() -> None:
    entries = build_entries(count=1)
    reservations = RecordingReservations()
    window = SubmissionWindow(capacity=1, reservations=reservations)
    window.replace_candidates(entries=entries)
    await window.take()

    window.complete(flow_run_id=entries[0].flow_run.id)

    assert reservations.released == []


async def test_failed_reservation_does_not_hold_a_slot() -> None:
    window = SubmissionWindow(capacity=1, reservations=UnreachableReservations())
    window.replace_candidates(entries=build_entries(count=1))

    with pytest.raises(ConnectionError):
        await window.take()

    assert window.in_flight == 0


async def test_reservation_lost_mid_batch_frees_the_slots_of_the_whole_batch() -> None:
    entries = build_entries(count=3)
    reservations = ReservationsLostMidBatch(successes=2)
    window = SubmissionWindow(capacity=3, reservations=reservations)
    window.replace_candidates(entries=entries)

    with pytest.raises(ConnectionError, match=r"^cache unreachable$"):
        await window.take()

    assert reservations.reserved == ids(entries[:2])
    assert window.in_flight == 0


async def test_failed_release_still_frees_the_slot_of_every_unsubmitted_run() -> None:
    entries = build_entries(count=2)
    window = SubmissionWindow(capacity=2, reservations=UnreleasableReservations())
    window.replace_candidates(entries=entries)
    await window.take()

    with pytest.raises(ConnectionError, match=r"^cache unreachable$"):
        await window.return_unsubmitted(flow_run_ids=ids(entries))

    assert window.in_flight == 0
