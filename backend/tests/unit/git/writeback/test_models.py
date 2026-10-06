from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from infrahub.core.constants import FullRegenerationReason, RepositoryDeliveryStatus
from infrahub.git.writeback.constants import REMOVED_ENTRY_IDS_KEPT
from infrahub.git.writeback.models import (
    AbandonmentRecord,
    DeliveryProgress,
    DeliveryQueue,
    HeldItem,
    HeldPythonAttribute,
    HeldRegeneration,
    HeldWiden,
    HoldReceipt,
    PendingMerge,
    ReleaseLease,
    WritebackIntent,
)

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
LEASE_DURATION = timedelta(minutes=15)
COMMIT = "0123456789abcdef0123456789abcdef01234567"
DELIVERED_COMMIT = "89abcdef0123456789abcdef0123456789abcdef"


def _entry(entry_id: str, source_git_branch: str = "feature") -> PendingMerge:
    return PendingMerge(
        entry_id=entry_id,
        source_branch=source_git_branch,
        source_git_branch=source_git_branch,
        source_commit=COMMIT,
        merged_at=NOW,
    )


def _queued(*entries: PendingMerge) -> DeliveryQueue:
    queue = DeliveryQueue()
    for entry in entries:
        appended = queue.with_entry(entry=entry, last_abandonment=None)
        assert appended is not None
        queue = appended
    return queue


def _hold_artifacts(held: HeldRegeneration, *ids: str) -> HeldRegeneration:
    updated, _ = held.with_hold(
        held=HeldRegeneration(artifact_definitions=tuple(HeldItem(id=item_id, hold_seq=0) for item_id in ids))
    )
    return updated


def _widen(hold_seq: int) -> HeldWiden:
    return HeldWiden(scope="all", reason=FullRegenerationReason.UNHELD_FOLLOW_UP, hold_seq=hold_seq)


def _hold_widen(held: HeldRegeneration) -> HeldRegeneration:
    updated, _ = held.with_hold(held=HeldRegeneration(widen=_widen(hold_seq=0)))
    return updated


def _take_lease(
    held: HeldRegeneration, lease_id: str, now: datetime, max_hold_seq: int | None = None
) -> tuple[HeldRegeneration, ReleaseLease]:
    lease = ReleaseLease.over(
        lease_id=lease_id,
        window=held.lease_window(now=now, max_hold_seq=max_hold_seq),
        expires_at=now + LEASE_DURATION,
    )
    return held.with_lease(lease=lease, now=now), lease


def _artifacts(*items: tuple[str, int]) -> tuple[HeldItem, ...]:
    return tuple(HeldItem(id=item_id, hold_seq=hold_seq) for item_id, hold_seq in items)


def _lease(lease_id: str, held: HeldRegeneration) -> ReleaseLease:
    return next(lease for lease in held.release_leases if lease.lease_id == lease_id)


def test_append_of_a_queued_id_changes_nothing() -> None:
    queue = _queued(_entry("e1"))

    assert queue.with_entry(entry=_entry("e1"), last_abandonment=None) is None
    assert queue.entries == (_entry("e1"),)
    assert queue.version == 1


def test_append_refuses_an_id_that_left_the_queue() -> None:
    queue = _queued(_entry("e1")).without_entries(entry_ids=["e1"])

    assert queue.entries == ()
    assert queue.with_entry(entry=_entry("e1"), last_abandonment=None) is None


def test_append_refuses_an_id_of_the_last_abandonment() -> None:
    record = AbandonmentRecord(
        abandoned_at=NOW,
        account_id="account-1",
        account_name="admin",
        queue_version=1,
        recorded_commit=COMMIT,
        entries=(_entry("e1"),),
    )

    assert DeliveryQueue().with_entry(entry=_entry("e1"), last_abandonment=record) is None
    appended = DeliveryQueue().with_entry(entry=_entry("e2"), last_abandonment=record)
    assert appended is not None
    assert appended.entries == (_entry("e2"),)


def test_removed_entry_ids_keep_only_the_most_recent() -> None:
    count = REMOVED_ENTRY_IDS_KEPT + 2
    ids = [f"e{index}" for index in range(count)]
    queue = _queued(*(_entry(entry_id) for entry_id in ids)).without_entries(entry_ids=ids)

    assert queue.removed_entry_ids == tuple(ids[2:])
    assert queue.with_entry(entry=_entry("e0"), last_abandonment=None) is not None
    assert queue.with_entry(entry=_entry("e2"), last_abandonment=None) is None


def test_version_moves_only_when_an_entry_joins_or_leaves() -> None:
    added = _queued(_entry("e1"))
    flagged = added.with_branch_deletion_requested(git_branch="feature")
    assert flagged is not None
    unknown_removed = flagged.without_entries(entry_ids=["unknown"])
    removed = flagged.without_entries(entry_ids=["e1"])

    assert flagged.entries[0].delete_source_git_branch is True
    assert [added.version, flagged.version, unknown_removed.version, removed.version] == [1, 1, 1, 2]


def test_branch_deletion_request_flags_only_the_entries_of_that_branch() -> None:
    queue = _queued(_entry("e1", source_git_branch="feature"), _entry("e2", source_git_branch="other"))

    flagged = queue.with_branch_deletion_requested(git_branch="feature")

    assert flagged is not None
    assert [entry.delete_source_git_branch for entry in flagged.entries] == [True, False]
    assert queue.with_branch_deletion_requested(git_branch="unknown") is None


def test_hold_raises_the_sequence_of_a_repeated_identifier_and_reports_the_previous_one() -> None:
    python_attribute = HeldPythonAttribute(kind="InfraDevice", attribute="description", hold_seq=0)
    held, first = HeldRegeneration().with_hold(
        held=HeldRegeneration(
            artifact_definitions=_artifacts(("a1", 0)),
            generator_definitions=(HeldItem(id="g1", hold_seq=0),),
            python_attributes=(python_attribute,),
        )
    )
    held, second = held.with_hold(
        held=HeldRegeneration(artifact_definitions=_artifacts(("a1", 0)), python_attributes=(python_attribute,))
    )

    assert first == HoldReceipt(hold_seq=1, previous_seqs={})
    assert second == HoldReceipt(hold_seq=2, previous_seqs={"a1": 1, "InfraDevice.description": 1})
    assert held.artifact_definitions == _artifacts(("a1", 2))
    assert held.generator_definitions == (HeldItem(id="g1", hold_seq=1),)
    assert held.python_attributes == (HeldPythonAttribute(kind="InfraDevice", attribute="description", hold_seq=2),)
    assert held.next_hold_seq == 3


@dataclass
class WidenHoldTestCase:
    name: str
    first: HeldWiden
    second: HeldWiden
    expected: HeldWiden


WIDEN_HOLD_TEST_CASES: list[WidenHoldTestCase] = [
    WidenHoldTestCase(
        name="wider_scope_replaces_narrower_scope",
        first=HeldWiden(scope="terminals", reason=FullRegenerationReason.SELECTION_FAILED, hold_seq=0),
        second=HeldWiden(scope="all", reason=FullRegenerationReason.UNHELD_FOLLOW_UP, hold_seq=0),
        expected=HeldWiden(scope="all", reason=FullRegenerationReason.UNHELD_FOLLOW_UP, hold_seq=2),
    ),
    WidenHoldTestCase(
        name="narrower_hold_keeps_wider_scope_and_its_reason",
        first=HeldWiden(scope="all", reason=FullRegenerationReason.FEATURE_DISABLED, hold_seq=0),
        second=HeldWiden(scope="terminals", reason=FullRegenerationReason.SELECTION_FAILED, hold_seq=0),
        expected=HeldWiden(scope="all", reason=FullRegenerationReason.FEATURE_DISABLED, hold_seq=2),
    ),
    WidenHoldTestCase(
        name="same_scope_takes_reason_of_latest_hold",
        first=HeldWiden(scope="all", reason=FullRegenerationReason.FEATURE_DISABLED, hold_seq=0),
        second=HeldWiden(scope="all", reason=FullRegenerationReason.UNHELD_FOLLOW_UP, hold_seq=0),
        expected=HeldWiden(scope="all", reason=FullRegenerationReason.UNHELD_FOLLOW_UP, hold_seq=2),
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in WIDEN_HOLD_TEST_CASES])
def test_repeated_widen_hold_keeps_one_marker(test_case: WidenHoldTestCase) -> None:
    held, _ = HeldRegeneration().with_hold(held=HeldRegeneration(widen=test_case.first))
    held, _ = held.with_hold(held=HeldRegeneration(widen=test_case.second))

    assert held.widen == test_case.expected


def test_lease_window_skips_items_of_a_live_lease_and_returns_items_of_an_expired_one() -> None:
    widen = HeldWiden(scope="all", reason=FullRegenerationReason.UNHELD_FOLLOW_UP, hold_seq=4)
    held = HeldRegeneration(
        next_hold_seq=5,
        artifact_definitions=_artifacts(("a1", 1), ("a2", 2)),
        generator_definitions=(HeldItem(id="g1", hold_seq=3),),
        widen=widen,
        release_leases=(
            ReleaseLease(
                lease_id="live",
                expires_at=NOW + timedelta(minutes=1),
                artifact_definitions=_artifacts(("a1", 1)),
                widen=widen,
            ),
            ReleaseLease(lease_id="expired", expires_at=NOW, artifact_definitions=_artifacts(("a2", 2))),
        ),
    )

    assert held.lease_window(now=NOW, max_hold_seq=None) == HeldRegeneration(
        artifact_definitions=_artifacts(("a2", 2)), generator_definitions=(HeldItem(id="g1", hold_seq=3),)
    )


def test_lease_window_leaves_out_items_held_after_the_bound() -> None:
    held = HeldRegeneration(
        next_hold_seq=4,
        artifact_definitions=_artifacts(("a1", 1), ("a2", 3)),
        widen=HeldWiden(scope="terminals", reason=FullRegenerationReason.SELECTION_FAILED, hold_seq=2),
    )

    assert held.lease_window(now=NOW, max_hold_seq=1) == HeldRegeneration(artifact_definitions=_artifacts(("a1", 1)))


def _expired_lease_live_lease_and_new_holds() -> tuple[HeldRegeneration, ReleaseLease, datetime]:
    """Lease A expires while lease B, taken a minute later, is still live, and new holds follow B."""
    held = _hold_artifacts(HeldRegeneration(), "a1", "a2")
    held, _ = _take_lease(held, "A", NOW)
    held = _hold_artifacts(held, "b1", "b2")
    held, lease_b = _take_lease(held, "B", NOW + timedelta(minutes=1))
    after_a_expired = NOW + LEASE_DURATION + timedelta(seconds=30)
    held = _hold_artifacts(held, "n1")
    return held, lease_b, after_a_expired


def test_new_lease_skips_the_live_lease_and_names_the_expired_lease_and_the_new_holds() -> None:
    held, _, now = _expired_lease_live_lease_and_new_holds()

    held, lease_c = _take_lease(held, "C", now)

    assert lease_c.window == HeldRegeneration(artifact_definitions=_artifacts(("a1", 1), ("a2", 1), ("n1", 3)))
    assert [lease.lease_id for lease in held.release_leases] == ["B", "C"]


def test_new_lease_never_names_items_of_a_live_lease_whose_clear_still_removes_them() -> None:
    held, lease_b, now = _expired_lease_live_lease_and_new_holds()
    held, _ = _take_lease(held, "C", now)

    after_c = held.without_window(lease_id="C", now=now)
    after_b = after_c.without_window(lease_id="B", now=now)

    assert after_c.artifact_definitions == lease_b.artifact_definitions == _artifacts(("b1", 2), ("b2", 2))
    assert after_c.release_leases == (lease_b,)
    assert after_b.artifact_definitions == ()
    assert after_b.release_leases == ()


def test_item_held_again_after_the_lease_survives_its_clear_and_goes_to_the_next_lease() -> None:
    held = _hold_artifacts(HeldRegeneration(), "a1", "a2")
    held, _ = _take_lease(held, "L", NOW)
    held = _hold_artifacts(held, "a1")

    held = held.without_window(lease_id="L", now=NOW)
    _, next_lease = _take_lease(held, "M", NOW)

    assert held.artifact_definitions == _artifacts(("a1", 2))
    assert held.release_leases == ()
    assert next_lease.artifact_definitions == _artifacts(("a1", 2))


def test_new_lease_moves_items_out_of_an_expired_lease_and_removes_it_once_empty() -> None:
    held = _hold_artifacts(HeldRegeneration(), "a1")
    held = _hold_artifacts(held, "a2")
    held, _ = _take_lease(held, "E", NOW)
    held = held.with_lease_expiry(lease_id="E", expires_at=NOW)

    held, lease_n = _take_lease(held, "N", NOW, max_hold_seq=1)

    assert lease_n.artifact_definitions == _artifacts(("a1", 1))
    assert _lease("E", held).artifact_definitions == _artifacts(("a2", 2))

    held, lease_m = _take_lease(held, "M", NOW)

    assert lease_m.artifact_definitions == _artifacts(("a2", 2))
    assert [lease.lease_id for lease in held.release_leases] == ["N", "M"]


def test_expired_lease_drops_an_item_no_longer_held_at_the_named_sequence() -> None:
    held = _hold_artifacts(HeldRegeneration(), "a1")
    held, _ = _take_lease(held, "E", NOW)
    held = _hold_artifacts(held, "a1")
    held, _ = _take_lease(held, "L", NOW + timedelta(minutes=1))
    held = _hold_artifacts(held, "b1")
    after_e_expired = NOW + LEASE_DURATION + timedelta(seconds=30)
    assert _lease("E", held).artifact_definitions == _artifacts(("a1", 1))

    held, lease_n = _take_lease(held, "N", after_e_expired)

    assert lease_n.artifact_definitions == _artifacts(("b1", 3))
    assert [lease.lease_id for lease in held.release_leases] == ["L", "N"]


def test_late_clear_of_an_expired_lease_removes_only_what_it_still_names() -> None:
    held = _hold_artifacts(HeldRegeneration(), "a1")
    held = _hold_artifacts(held, "a2")
    held, _ = _take_lease(held, "E", NOW)
    held = held.with_lease_expiry(lease_id="E", expires_at=NOW)
    held, _ = _take_lease(held, "N", NOW, max_hold_seq=1)

    held = held.without_window(lease_id="E", now=NOW)

    assert held.artifact_definitions == _artifacts(("a1", 1))
    assert [lease.lease_id for lease in held.release_leases] == ["N"]
    assert held.without_window(lease_id="E", now=NOW) == held


def test_clear_removes_the_widen_marker_and_every_kind_of_item_that_the_lease_names() -> None:
    held, _ = HeldRegeneration().with_hold(
        held=HeldRegeneration(
            generator_definitions=(HeldItem(id="g1", hold_seq=0),),
            python_attributes=(HeldPythonAttribute(kind="InfraDevice", attribute="description", hold_seq=0),),
            widen=_widen(hold_seq=0),
        )
    )
    held, lease = _take_lease(held, "L", NOW)

    cleared = held.without_window(lease_id="L", now=NOW)

    assert lease.window == HeldRegeneration(
        generator_definitions=(HeldItem(id="g1", hold_seq=1),),
        python_attributes=(HeldPythonAttribute(kind="InfraDevice", attribute="description", hold_seq=1),),
        widen=_widen(hold_seq=1),
    )
    assert cleared == HeldRegeneration(next_hold_seq=2)


def test_widen_held_again_after_the_lease_survives_its_clear_and_goes_to_the_next_lease() -> None:
    held = _hold_widen(HeldRegeneration())
    held, lease = _take_lease(held, "L", NOW)
    held = _hold_widen(held)

    held = held.without_window(lease_id="L", now=NOW)
    _, next_lease = _take_lease(held, "M", NOW)

    assert lease.widen == _widen(hold_seq=1)
    assert held.widen == _widen(hold_seq=2)
    assert held.release_leases == ()
    assert next_lease.window == HeldRegeneration(widen=_widen(hold_seq=2))


def test_widen_of_an_expired_lease_moves_to_the_new_lease_and_the_emptied_lease_is_removed() -> None:
    held = _hold_widen(HeldRegeneration())
    held = _hold_artifacts(held, "a1")
    held, _ = _take_lease(held, "E", NOW)
    held = held.with_lease_expiry(lease_id="E", expires_at=NOW)

    held, lease_n = _take_lease(held, "N", NOW, max_hold_seq=1)

    assert lease_n.window == HeldRegeneration(widen=_widen(hold_seq=1))
    assert _lease("E", held).window == HeldRegeneration(artifact_definitions=_artifacts(("a1", 2)))

    held, lease_m = _take_lease(held, "M", NOW)

    assert lease_m.window == HeldRegeneration(artifact_definitions=_artifacts(("a1", 2)))
    assert [lease.lease_id for lease in held.release_leases] == ["N", "M"]


def _intent(
    *,
    status: RepositoryDeliveryStatus = RepositoryDeliveryStatus.PENDING,
    queue: DeliveryQueue | None = None,
    held: HeldRegeneration | None = None,
    progress: DeliveryProgress | None = None,
    last_delivered_commit: str | None = None,
) -> WritebackIntent:
    return WritebackIntent(
        repository_id="repository-1",
        status=status,
        cause=None,
        error=None,
        queue=queue if queue is not None else _queued(_entry("e1")),
        held=held if held is not None else HeldRegeneration(),
        progress=progress if progress is not None else DeliveryProgress(),
        last_delivered_commit=last_delivered_commit,
    )


def test_settle_without_a_delivered_commit_keeps_the_last_delivered_commit() -> None:
    intent = _intent(last_delivered_commit=DELIVERED_COMMIT)

    settled, lease = intent.with_delivery_settled(snapshot=intent, delivered_commit=None, lease_id="L", now=NOW)

    assert lease is None
    assert settled == _intent(
        status=RepositoryDeliveryStatus.NONE,
        queue=DeliveryQueue(version=2, removed_entry_ids=("e1",)),
        last_delivered_commit=DELIVERED_COMMIT,
    )


@dataclass
class StaleTestCase:
    name: str
    status: RepositoryDeliveryStatus
    progress_age: timedelta
    retry_due_in: timedelta | None
    lock_free: bool
    run_queued: bool
    expected: bool


STALE_TEST_CASES: list[StaleTestCase] = [
    StaleTestCase(
        name="every_condition_holds",
        status=RepositoryDeliveryStatus.PENDING,
        progress_age=timedelta(minutes=16),
        retry_due_in=None,
        lock_free=True,
        run_queued=False,
        expected=True,
    ),
    StaleTestCase(
        name="status_is_not_pending",
        status=RepositoryDeliveryStatus.ACTION_REQUIRED,
        progress_age=timedelta(minutes=16),
        retry_due_in=None,
        lock_free=True,
        run_queued=False,
        expected=False,
    ),
    StaleTestCase(
        name="retry_due_in_the_future",
        status=RepositoryDeliveryStatus.PENDING,
        progress_age=timedelta(minutes=16),
        retry_due_in=timedelta(minutes=1),
        lock_free=True,
        run_queued=False,
        expected=False,
    ),
    StaleTestCase(
        name="retry_due_in_the_past",
        status=RepositoryDeliveryStatus.PENDING,
        progress_age=timedelta(minutes=16),
        retry_due_in=-timedelta(minutes=1),
        lock_free=True,
        run_queued=False,
        expected=True,
    ),
    StaleTestCase(
        name="progress_within_the_stale_bound",
        status=RepositoryDeliveryStatus.PENDING,
        progress_age=timedelta(minutes=14),
        retry_due_in=None,
        lock_free=True,
        run_queued=False,
        expected=False,
    ),
    StaleTestCase(
        name="repository_lock_held",
        status=RepositoryDeliveryStatus.PENDING,
        progress_age=timedelta(minutes=16),
        retry_due_in=None,
        lock_free=False,
        run_queued=False,
        expected=False,
    ),
    StaleTestCase(
        name="delivery_run_waits_to_start",
        status=RepositoryDeliveryStatus.PENDING,
        progress_age=timedelta(minutes=16),
        retry_due_in=None,
        lock_free=True,
        run_queued=True,
        expected=False,
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in STALE_TEST_CASES])
def test_is_stale(test_case: StaleTestCase) -> None:
    intent = _intent(
        status=test_case.status,
        progress=DeliveryProgress(
            last_progress_at=NOW - test_case.progress_age,
            retry_due_at=NOW + test_case.retry_due_in if test_case.retry_due_in is not None else None,
        ),
    )

    assert (
        intent.is_stale(now=NOW, lock_free=test_case.lock_free, run_queued=test_case.run_queued) is test_case.expected
    )


@dataclass
class HasWorkTestCase:
    name: str
    queue: DeliveryQueue
    held: HeldRegeneration
    expected: bool


HAS_WORK_TEST_CASES: list[HasWorkTestCase] = [
    HasWorkTestCase(name="queued_entry", queue=_queued(_entry("e1")), held=HeldRegeneration(), expected=True),
    HasWorkTestCase(
        name="held_item_without_lease",
        queue=DeliveryQueue(),
        held=HeldRegeneration(artifact_definitions=_artifacts(("a1", 1))),
        expected=True,
    ),
    HasWorkTestCase(
        name="held_item_under_live_lease",
        queue=DeliveryQueue(),
        held=HeldRegeneration(
            artifact_definitions=_artifacts(("a1", 1)),
            release_leases=(
                ReleaseLease(
                    lease_id="live", expires_at=NOW + timedelta(minutes=1), artifact_definitions=_artifacts(("a1", 1))
                ),
            ),
        ),
        expected=False,
    ),
    HasWorkTestCase(
        name="held_item_under_expired_lease",
        queue=DeliveryQueue(),
        held=HeldRegeneration(
            artifact_definitions=_artifacts(("a1", 1)),
            release_leases=(
                ReleaseLease(lease_id="expired", expires_at=NOW, artifact_definitions=_artifacts(("a1", 1))),
            ),
        ),
        expected=True,
    ),
    HasWorkTestCase(name="nothing_queued_or_held", queue=DeliveryQueue(), held=HeldRegeneration(), expected=False),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in HAS_WORK_TEST_CASES])
def test_has_work(test_case: HasWorkTestCase) -> None:
    intent = _intent(queue=test_case.queue, held=test_case.held)

    assert intent.has_work(now=NOW) is test_case.expected


@dataclass
class InvalidSourceCommitTestCase:
    name: str
    source_commit: str


INVALID_SOURCE_COMMIT_TEST_CASES: list[InvalidSourceCommitTestCase] = [
    InvalidSourceCommitTestCase(name="abbreviated", source_commit="0123456"),
    InvalidSourceCommitTestCase(name="too_long", source_commit=COMMIT + "8"),
    InvalidSourceCommitTestCase(name="upper_case", source_commit=COMMIT.upper()),
    InvalidSourceCommitTestCase(name="not_hexadecimal", source_commit="g" * 40),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in INVALID_SOURCE_COMMIT_TEST_CASES])
def test_source_commit_must_be_a_full_lower_case_sha(test_case: InvalidSourceCommitTestCase) -> None:
    with pytest.raises(ValidationError, match=r"\nsource_commit\n.*'\^\[0-9a-f\]\{40\}\$'"):
        PendingMerge(
            entry_id="e1",
            source_branch="feature",
            source_git_branch="feature",
            source_commit=test_case.source_commit,
            merged_at=NOW,
        )
