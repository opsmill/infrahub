from __future__ import annotations

import asyncio
import re
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import (
    AccountType,
    FullRegenerationReason,
    InfrahubKind,
    RepositoryDeliveryFailureCause,
    RepositoryDeliveryStatus,
)
from infrahub.core.node import Node
from infrahub.exceptions import DeliveryQueueChangedError, DeliveryStateUnavailableError, NothingPendingError
from infrahub.git.writeback.constants import RELEASE_LEASE_SECONDS, STATE_LOCK_TTL_SECONDS
from infrahub.git.writeback.models import (
    AbandonmentRecord,
    Actor,
    DeliveryFailure,
    DeliveryProgress,
    DeliveryQueue,
    HeldItem,
    HeldRegeneration,
    HeldWiden,
    HoldReceipt,
    ReleaseLease,
    RevertedDelivery,
    WritebackIntent,
)
from infrahub.git.writeback.store import STATE_LOCK_NAMESPACE

from .conftest import (
    DELIVERED_COMMIT,
    ERROR,
    FAILURE_CAUSE,
    HELD_REGENERATION,
    LAST_ABANDONMENT,
    LAST_DELIVERED_COMMIT,
    NOW,
    PROGRESS,
    QUEUE,
    REVERTED,
    SOURCE_COMMIT,
    STATUS,
    create_repository,
    pending_merge,
)

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase
    from infrahub.git.writeback.models import PendingMerge

    from .conftest import StoreUnderTest

LEASE_DURATION = timedelta(seconds=RELEASE_LEASE_SECONDS)
RECORDED_COMMIT = "fedcba9876543210fedcba9876543210fedcba98"

UNREACHABLE = DeliveryFailure(
    cause=RepositoryDeliveryFailureCause.REMOTE_UNREACHABLE, retryable=True, message="The remote did not answer."
)
REFUSED = DeliveryFailure(
    cause=RepositoryDeliveryFailureCause.PERMISSION, retryable=False, message="remote: branch main is protected"
)
RELEASE_FAILED = DeliveryFailure(
    cause=None, retryable=True, message="The release step of the delivery failed with DatabaseError."
)


def _artifacts(*definition_ids: str) -> HeldRegeneration:
    return HeldRegeneration(artifact_definitions=tuple(HeldItem(id=item, hold_seq=0) for item in definition_ids))


def _empty_intent(repository_id: str) -> WritebackIntent:
    return WritebackIntent(
        repository_id=repository_id,
        status=RepositoryDeliveryStatus.NONE,
        cause=None,
        error=None,
        queue=DeliveryQueue(),
        held=HeldRegeneration(),
        progress=DeliveryProgress(),
        last_delivered_commit=None,
    )


async def _enqueue(subject: StoreUnderTest, *entries: PendingMerge) -> None:
    for entry in entries:
        await subject.store.enqueue(repository_id=subject.repository_id, entry=entry, widen=False)


async def _hold(subject: StoreUnderTest, *definition_ids: str) -> HoldReceipt | None:
    return await subject.store.hold(repository_id=subject.repository_id, held=_artifacts(*definition_ids))


async def test_read_gives_the_empty_state_of_a_repository_that_never_delivered(subject: StoreUnderTest) -> None:
    assert await subject.read() == _empty_intent(subject.repository_id)
    assert subject.timeline.events == []


async def test_enqueue_appends_the_merge_and_sets_pending(subject: StoreUnderTest) -> None:
    entry = pending_merge("e1")

    async with subject.expect_transition(saved={STATUS, QUEUE, PROGRESS}):
        returned = await subject.store.enqueue(repository_id=subject.repository_id, entry=entry, widen=False)

    expected = WritebackIntent(
        repository_id=subject.repository_id,
        status=RepositoryDeliveryStatus.PENDING,
        cause=None,
        error=None,
        queue=DeliveryQueue(version=1, entries=(entry,)),
        held=HeldRegeneration(),
        progress=DeliveryProgress(last_progress_at=NOW),
        last_delivered_commit=None,
    )
    assert returned == expected
    assert await subject.read() == expected


async def test_enqueue_with_widen_holds_a_full_regeneration_in_the_same_save(subject: StoreUnderTest) -> None:
    async with subject.expect_transition(saved={STATUS, QUEUE, HELD_REGENERATION, PROGRESS}):
        await subject.store.enqueue(repository_id=subject.repository_id, entry=pending_merge("e1"), widen=True)

    assert (await subject.read()).held == HeldRegeneration(
        next_hold_seq=2,
        widen=HeldWiden(scope="all", reason=FullRegenerationReason.UNHELD_FOLLOW_UP, hold_seq=1),
    )


async def test_enqueue_of_a_queued_id_writes_nothing_and_holds_no_regeneration(subject: StoreUnderTest) -> None:
    entry = pending_merge("e1")
    await _enqueue(subject, entry)
    before = await subject.read()
    subject.clock.advance(seconds=60)

    async with subject.expect_transition(saved=set()):
        returned = await subject.store.enqueue(repository_id=subject.repository_id, entry=entry, widen=True)

    assert returned == before
    assert await subject.read() == before


async def test_enqueue_after_a_final_failure_sets_pending_and_keeps_the_cause_and_the_error(
    subject: StoreUnderTest,
) -> None:
    first, second = pending_merge("e1"), pending_merge("e2", source_git_branch="feature-2")
    await _enqueue(subject, first)
    await subject.store.record_failure(
        repository_id=subject.repository_id, failure=REFUSED, final=True, retry_due_at=None
    )
    assert (await subject.read()).status == RepositoryDeliveryStatus.ACTION_REQUIRED
    subject.clock.advance(seconds=60)

    async with subject.expect_transition(saved={STATUS, QUEUE, PROGRESS}):
        returned = await subject.store.enqueue(repository_id=subject.repository_id, entry=second, widen=False)

    expected = WritebackIntent(
        repository_id=subject.repository_id,
        status=RepositoryDeliveryStatus.PENDING,
        cause=RepositoryDeliveryFailureCause.PERMISSION,
        error="remote: branch main is protected",
        queue=DeliveryQueue(version=2, entries=(first, second)),
        held=HeldRegeneration(),
        progress=DeliveryProgress(last_progress_at=NOW + timedelta(seconds=60)),
        last_delivered_commit=None,
    )
    assert returned == expected
    assert await subject.read() == expected


async def test_start_attempt_clears_the_waiting_retry_and_keeps_the_cause(subject: StoreUnderTest) -> None:
    await _enqueue(subject, pending_merge("e1"))
    await subject.store.record_failure(
        repository_id=subject.repository_id, failure=UNREACHABLE, final=False, retry_due_at=NOW + timedelta(seconds=30)
    )
    subject.clock.advance(seconds=30)

    async with subject.expect_transition(saved={PROGRESS}):
        snapshot = await subject.store.start_attempt(repository_id=subject.repository_id)

    started_at = NOW + timedelta(seconds=30)
    assert snapshot.status == RepositoryDeliveryStatus.PENDING
    assert (snapshot.cause, snapshot.error) == (UNREACHABLE.cause, UNREACHABLE.message)
    assert snapshot.progress == DeliveryProgress(last_progress_at=started_at, attempt_started_at=started_at)
    assert await subject.read() == snapshot


async def test_start_attempt_after_a_final_failure_sets_pending(subject: StoreUnderTest) -> None:
    await _enqueue(subject, pending_merge("e1"))
    await subject.store.record_failure(
        repository_id=subject.repository_id, failure=REFUSED, final=True, retry_due_at=None
    )

    async with subject.expect_transition(saved={STATUS, PROGRESS}):
        snapshot = await subject.store.start_attempt(repository_id=subject.repository_id)

    assert (snapshot.status, snapshot.cause) == (
        RepositoryDeliveryStatus.PENDING,
        RepositoryDeliveryFailureCause.PERMISSION,
    )


async def test_start_attempt_on_an_empty_queue_keeps_the_status(subject: StoreUnderTest) -> None:
    async with subject.expect_transition(saved={PROGRESS}):
        snapshot = await subject.store.start_attempt(repository_id=subject.repository_id)

    assert snapshot.status == RepositoryDeliveryStatus.NONE
    assert snapshot.progress == DeliveryProgress(last_progress_at=NOW, attempt_started_at=NOW)


async def test_retryable_failure_keeps_pending_and_sets_the_retry(subject: StoreUnderTest) -> None:
    await _enqueue(subject, pending_merge("e1"))
    subject.clock.advance(seconds=5)
    retry_due_at = NOW + timedelta(seconds=35)

    async with subject.expect_transition(saved={FAILURE_CAUSE, ERROR, PROGRESS}):
        await subject.store.record_failure(
            repository_id=subject.repository_id, failure=UNREACHABLE, final=False, retry_due_at=retry_due_at
        )

    intent = await subject.read()
    assert (intent.status, intent.cause, intent.error) == (
        RepositoryDeliveryStatus.PENDING,
        RepositoryDeliveryFailureCause.REMOTE_UNREACHABLE,
        "The remote did not answer.",
    )
    assert intent.progress == DeliveryProgress(last_progress_at=NOW + timedelta(seconds=5), retry_due_at=retry_due_at)


async def test_final_failure_sets_action_required_and_clears_the_retry(subject: StoreUnderTest) -> None:
    await _enqueue(subject, pending_merge("e1"))
    await subject.store.record_failure(
        repository_id=subject.repository_id, failure=UNREACHABLE, final=False, retry_due_at=NOW + timedelta(seconds=30)
    )
    subject.clock.advance(seconds=5)

    async with subject.expect_transition(saved={STATUS, FAILURE_CAUSE, ERROR, PROGRESS}):
        await subject.store.record_failure(
            repository_id=subject.repository_id, failure=REFUSED, final=True, retry_due_at=NOW + timedelta(seconds=90)
        )

    intent = await subject.read()
    assert (intent.status, intent.cause, intent.error) == (
        RepositoryDeliveryStatus.ACTION_REQUIRED,
        RepositoryDeliveryFailureCause.PERMISSION,
        "remote: branch main is protected",
    )
    assert intent.progress == DeliveryProgress(last_progress_at=NOW + timedelta(seconds=5))


async def test_failure_without_a_cause_keeps_the_stored_cause(subject: StoreUnderTest) -> None:
    await _enqueue(subject, pending_merge("e1"))
    await subject.store.record_failure(
        repository_id=subject.repository_id, failure=REFUSED, final=True, retry_due_at=None
    )

    async with subject.expect_transition(saved={ERROR}):
        await subject.store.record_failure(
            repository_id=subject.repository_id, failure=RELEASE_FAILED, final=False, retry_due_at=None
        )

    intent = await subject.read()
    assert (intent.status, intent.cause, intent.error) == (
        RepositoryDeliveryStatus.ACTION_REQUIRED,
        RepositoryDeliveryFailureCause.PERMISSION,
        "The release step of the delivery failed with DatabaseError.",
    )


async def test_final_failure_on_an_empty_queue_never_changes_the_status(subject: StoreUnderTest) -> None:
    async with subject.expect_transition(saved={FAILURE_CAUSE, ERROR, PROGRESS}):
        await subject.store.record_failure(
            repository_id=subject.repository_id, failure=REFUSED, final=True, retry_due_at=None
        )

    assert (await subject.read()).status == RepositoryDeliveryStatus.NONE


async def test_progress_and_touch_move_the_progress_and_leave_the_queue_untouched(subject: StoreUnderTest) -> None:
    await _enqueue(subject, pending_merge("e1"))
    queued = (await subject.read()).queue

    subject.clock.advance(seconds=10)
    async with subject.expect_transition(saved={PROGRESS}):
        await subject.store.progress(repository_id=subject.repository_id)
    assert (await subject.read()).progress == DeliveryProgress(last_progress_at=NOW + timedelta(seconds=10))

    subject.clock.advance(seconds=10)
    async with subject.expect_transition(saved={PROGRESS}):
        await subject.store.touch(repository_id=subject.repository_id)

    intent = await subject.read()
    assert intent.progress == DeliveryProgress(last_progress_at=NOW + timedelta(seconds=20))
    assert intent.queue == queued


async def test_owed_import_is_saved_then_settled(subject: StoreUnderTest) -> None:
    entry = pending_merge("e1")
    await _enqueue(subject, entry)
    snapshot = await subject.store.start_attempt(repository_id=subject.repository_id)

    async with subject.expect_transition(saved={QUEUE}):
        await subject.store.owe_import(repository_id=subject.repository_id, commit=DELIVERED_COMMIT)
    assert (await subject.read()).queue == DeliveryQueue(
        version=1, entries=(entry,), import_owed_commit=DELIVERED_COMMIT
    )

    async with subject.expect_transition(saved={QUEUE}):
        settled = await subject.store.settle_import(
            repository_id=subject.repository_id, commit=DELIVERED_COMMIT, snapshot=snapshot
        )

    assert settled is True
    assert (await subject.read()).queue == DeliveryQueue(version=1, entries=(entry,))


async def test_owed_import_stays_when_the_queue_grew_or_another_commit_is_owed(subject: StoreUnderTest) -> None:
    await _enqueue(subject, pending_merge("e1"))
    snapshot = await subject.store.start_attempt(repository_id=subject.repository_id)
    await subject.store.owe_import(repository_id=subject.repository_id, commit=DELIVERED_COMMIT)
    await _enqueue(subject, pending_merge("e2"))

    async with subject.expect_transition(saved=set()):
        grown = await subject.store.settle_import(
            repository_id=subject.repository_id, commit=DELIVERED_COMMIT, snapshot=snapshot
        )
    async with subject.expect_transition(saved=set()):
        other = await subject.store.settle_import(
            repository_id=subject.repository_id, commit=RECORDED_COMMIT, snapshot=await subject.read()
        )

    assert (grown, other) == (False, False)
    assert (await subject.read()).queue.import_owed_commit == DELIVERED_COMMIT


async def test_branch_deletion_flags_the_entries_of_the_branch_without_moving_the_version(
    subject: StoreUnderTest,
) -> None:
    first, second = (
        pending_merge("e1", source_git_branch="feature-1"),
        pending_merge("e2", source_git_branch="feature-2"),
    )
    await _enqueue(subject, first, second)

    async with subject.expect_transition(saved={QUEUE}):
        flagged = await subject.store.request_branch_deletion(
            repository_id=subject.repository_id, git_branch="feature-1"
        )
    async with subject.expect_transition(saved=set()):
        unknown = await subject.store.request_branch_deletion(
            repository_id=subject.repository_id, git_branch="feature-3"
        )

    assert (flagged, unknown) == (True, False)
    assert (await subject.read()).queue == DeliveryQueue(
        version=2, entries=(first.model_copy(update={"delete_source_git_branch": True}), second)
    )


async def test_hold_on_an_empty_queue_writes_nothing(subject: StoreUnderTest) -> None:
    async with subject.expect_transition(saved=set()):
        receipt = await _hold(subject, "artifact-1")

    assert receipt is None
    assert (await subject.read()).held == HeldRegeneration()


async def test_hold_takes_the_next_sequence_and_reports_the_previous_one(subject: StoreUnderTest) -> None:
    await _enqueue(subject, pending_merge("e1"))

    async with subject.expect_transition(saved={HELD_REGENERATION}):
        first = await _hold(subject, "artifact-1")
    async with subject.expect_transition(saved={HELD_REGENERATION}):
        second = await _hold(subject, "artifact-1", "artifact-2")

    assert first == HoldReceipt(hold_seq=1, previous_seqs={})
    assert second == HoldReceipt(hold_seq=2, previous_seqs={"artifact-1": 1})
    assert (await subject.read()).held == HeldRegeneration(
        next_hold_seq=3,
        artifact_definitions=(HeldItem(id="artifact-1", hold_seq=2), HeldItem(id="artifact-2", hold_seq=2)),
    )


async def test_settle_delivery_empties_the_queue_and_leases_the_held_items(subject: StoreUnderTest) -> None:
    await _enqueue(subject, pending_merge("e1"))
    await _hold(subject, "artifact-1")
    await subject.store.record_failure(
        repository_id=subject.repository_id, failure=UNREACHABLE, final=False, retry_due_at=None
    )
    snapshot = await subject.store.start_attempt(repository_id=subject.repository_id)
    subject.clock.advance(seconds=60)

    async with subject.expect_transition(
        saved={STATUS, FAILURE_CAUSE, ERROR, QUEUE, HELD_REGENERATION, LAST_DELIVERED_COMMIT}
    ):
        lease = await subject.store.settle_delivery(
            repository_id=subject.repository_id, snapshot=snapshot, delivered_commit=DELIVERED_COMMIT
        )

    assert lease is not None
    assert lease == ReleaseLease(
        lease_id=lease.lease_id,
        expires_at=NOW + timedelta(seconds=60) + LEASE_DURATION,
        artifact_definitions=(HeldItem(id="artifact-1", hold_seq=1),),
    )
    intent = await subject.read()
    assert (intent.status, intent.cause, intent.error, intent.last_delivered_commit) == (
        RepositoryDeliveryStatus.NONE,
        None,
        None,
        DELIVERED_COMMIT,
    )
    assert intent.queue == DeliveryQueue(version=2, removed_entry_ids=("e1",))
    assert intent.held == HeldRegeneration(
        next_hold_seq=2, artifact_definitions=(HeldItem(id="artifact-1", hold_seq=1),), release_leases=(lease,)
    )


async def test_settle_delivery_keeps_the_merges_and_the_holds_that_came_after_the_snapshot(
    subject: StoreUnderTest,
) -> None:
    later = pending_merge("e2")
    await _enqueue(subject, pending_merge("e1"))
    await _hold(subject, "artifact-1")
    await subject.store.record_failure(
        repository_id=subject.repository_id, failure=UNREACHABLE, final=False, retry_due_at=None
    )
    snapshot = await subject.store.start_attempt(repository_id=subject.repository_id)
    await _enqueue(subject, later)
    await _hold(subject, "artifact-2")

    async with subject.expect_transition(saved={QUEUE, HELD_REGENERATION}):
        lease = await subject.store.settle_delivery(
            repository_id=subject.repository_id, snapshot=snapshot, delivered_commit=None
        )

    assert lease is not None
    assert lease.window == HeldRegeneration(artifact_definitions=(HeldItem(id="artifact-1", hold_seq=1),))
    intent = await subject.read()
    assert (intent.status, intent.cause) == (
        RepositoryDeliveryStatus.PENDING,
        RepositoryDeliveryFailureCause.REMOTE_UNREACHABLE,
    )
    assert intent.queue == DeliveryQueue(version=3, entries=(later,), removed_entry_ids=("e1",))


async def test_settle_delivery_without_held_items_takes_no_lease(subject: StoreUnderTest) -> None:
    await _enqueue(subject, pending_merge("e1"))
    snapshot = await subject.store.start_attempt(repository_id=subject.repository_id)

    async with subject.expect_transition(saved={STATUS, QUEUE}):
        lease = await subject.store.settle_delivery(
            repository_id=subject.repository_id, snapshot=snapshot, delivered_commit=None
        )

    assert lease is None
    assert (await subject.read()).held == HeldRegeneration()


async def test_abandon_drops_the_queue_with_its_record_and_names_the_account(
    db: InfrahubDatabase, subject: StoreUnderTest
) -> None:
    account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT, branch=subject.branch)
    await account.new(db=db, name="release-manager", account_type=AccountType.USER.value, password="Abandon-123")
    await account.save(db=db)
    first, second = pending_merge("e1"), pending_merge("e2", source_git_branch="feature-2")
    await _enqueue(subject, first, second)
    await _hold(subject, "artifact-1")
    await subject.store.owe_import(repository_id=subject.repository_id, commit=DELIVERED_COMMIT)
    await subject.store.record_failure(
        repository_id=subject.repository_id, failure=REFUSED, final=True, retry_due_at=None
    )
    record = AbandonmentRecord(
        abandoned_at=NOW,
        account_id=account.id,
        account_name="release-manager",
        queue_version=2,
        recorded_commit=RECORDED_COMMIT,
    )

    async with subject.expect_transition(
        saved={STATUS, FAILURE_CAUSE, ERROR, QUEUE, HELD_REGENERATION, LAST_ABANDONMENT}, user_id=account.id
    ):
        abandoned, lease = await subject.store.abandon(
            repository_id=subject.repository_id,
            queue_version=2,
            record=record,
            actor=Actor(account_id=account.id, account_name="release-manager"),
        )

    assert lease is not None
    assert lease.window == HeldRegeneration(artifact_definitions=(HeldItem(id="artifact-1", hold_seq=1),))
    assert abandoned == await subject.read()
    assert (abandoned.status, abandoned.cause, abandoned.error) == (RepositoryDeliveryStatus.NONE, None, None)
    assert abandoned.queue == DeliveryQueue(version=3, removed_entry_ids=("e1", "e2"))
    assert abandoned.last_abandonment == record.model_copy(
        update={"entries": (first, second), "import_owed_commit": DELIVERED_COMMIT}
    )


async def test_abandon_refuses_a_queue_that_changed_and_writes_nothing(subject: StoreUnderTest) -> None:
    await _enqueue(subject, pending_merge("e1"))
    before = await subject.read()
    record = AbandonmentRecord(
        abandoned_at=NOW,
        account_id="account-1",
        account_name="someone",
        queue_version=0,
        recorded_commit=RECORDED_COMMIT,
    )

    async with subject.expect_transition(saved=set()):
        with pytest.raises(
            DeliveryQueueChangedError,
            match=r"^The pending pushes of repository delivery-repository changed since version 0; reload and try again\.$",
        ):
            await subject.store.abandon(
                repository_id=subject.repository_id,
                queue_version=0,
                record=record,
                actor=Actor(account_id="account-1", account_name="someone"),
            )

    assert await subject.read() == before


async def test_abandon_refuses_an_empty_queue(subject: StoreUnderTest) -> None:
    record = AbandonmentRecord(
        abandoned_at=NOW,
        account_id="account-1",
        account_name="someone",
        queue_version=0,
        recorded_commit=RECORDED_COMMIT,
    )

    async with subject.expect_transition(saved=set()):
        with pytest.raises(
            NothingPendingError, match=r"^Repository delivery-repository has nothing pending to push\.$"
        ):
            await subject.store.abandon(
                repository_id=subject.repository_id,
                queue_version=0,
                record=record,
                actor=Actor(account_id="account-1", account_name="someone"),
            )

    assert await subject.read() == _empty_intent(subject.repository_id)


async def _settle_with_a_hold_after_the_snapshot(subject: StoreUnderTest, *definition_ids: str) -> None:
    """Leave the held items behind an empty queue, uncovered by any lease."""
    await _enqueue(subject, pending_merge("e1"))
    snapshot = await subject.store.start_attempt(repository_id=subject.repository_id)
    await _hold(subject, *definition_ids)
    assert (
        await subject.store.settle_delivery(
            repository_id=subject.repository_id, snapshot=snapshot, delivered_commit=None
        )
        is None
    )


async def test_owed_release_leases_every_uncovered_item_once(subject: StoreUnderTest) -> None:
    await _settle_with_a_hold_after_the_snapshot(subject, "artifact-1")

    async with subject.expect_transition(saved={HELD_REGENERATION}):
        lease = await subject.store.lease_owed_release(repository_id=subject.repository_id)
    async with subject.expect_transition(saved=set()):
        covered = await subject.store.lease_owed_release(repository_id=subject.repository_id)

    assert lease is not None
    assert lease == ReleaseLease(
        lease_id=lease.lease_id,
        expires_at=NOW + LEASE_DURATION,
        artifact_definitions=(HeldItem(id="artifact-1", hold_seq=1),),
    )
    assert covered is None


async def test_owed_release_takes_no_lease_while_merges_are_queued(subject: StoreUnderTest) -> None:
    await _enqueue(subject, pending_merge("e1"))
    await _hold(subject, "artifact-1")

    async with subject.expect_transition(saved=set()):
        lease = await subject.store.lease_owed_release(repository_id=subject.repository_id)

    assert lease is None


async def test_renew_lease_moves_its_expiry(subject: StoreUnderTest) -> None:
    await _settle_with_a_hold_after_the_snapshot(subject, "artifact-1")
    lease = await subject.store.lease_owed_release(repository_id=subject.repository_id)
    assert lease is not None
    subject.clock.advance(seconds=300)

    async with subject.expect_transition(saved={HELD_REGENERATION}):
        await subject.store.renew_lease(repository_id=subject.repository_id, lease_id=lease.lease_id)
    async with subject.expect_transition(saved=set()):
        await subject.store.renew_lease(repository_id=subject.repository_id, lease_id="gone")

    assert (await subject.read()).held.release_leases == (
        lease.model_copy(update={"expires_at": NOW + timedelta(seconds=300) + LEASE_DURATION}),
    )


async def test_expired_lease_gives_its_items_to_the_next_lease_and_is_removed(subject: StoreUnderTest) -> None:
    await _settle_with_a_hold_after_the_snapshot(subject, "artifact-1")
    failed = await subject.store.lease_owed_release(repository_id=subject.repository_id)
    assert failed is not None
    subject.clock.advance(seconds=30)

    async with subject.expect_transition(saved={HELD_REGENERATION}):
        await subject.store.expire_lease(repository_id=subject.repository_id, lease_id=failed.lease_id)
    expired = await subject.read()
    assert expired.held.artifact_definitions == (HeldItem(id="artifact-1", hold_seq=1),)
    assert expired.held.release_leases == (failed.model_copy(update={"expires_at": NOW + timedelta(seconds=30)}),)

    async with subject.expect_transition(saved={HELD_REGENERATION}):
        next_lease = await subject.store.lease_owed_release(repository_id=subject.repository_id)

    assert next_lease is not None
    assert next_lease.window == HeldRegeneration(artifact_definitions=(HeldItem(id="artifact-1", hold_seq=1),))
    assert (await subject.read()).held.release_leases == (next_lease,)


async def test_clear_released_keeps_an_item_held_again_after_the_lease(subject: StoreUnderTest) -> None:
    await _enqueue(subject, pending_merge("e1"))
    await _hold(subject, "artifact-1", "artifact-2")
    snapshot = await subject.store.start_attempt(repository_id=subject.repository_id)
    lease = await subject.store.settle_delivery(
        repository_id=subject.repository_id, snapshot=snapshot, delivered_commit=DELIVERED_COMMIT
    )
    assert lease is not None
    await _enqueue(subject, pending_merge("e2"))
    await _hold(subject, "artifact-1")

    async with subject.expect_transition(saved={HELD_REGENERATION}):
        await subject.store.clear_released(repository_id=subject.repository_id, lease_id=lease.lease_id)
    async with subject.expect_transition(saved=set()):
        await subject.store.clear_released(repository_id=subject.repository_id, lease_id=lease.lease_id)

    assert (await subject.read()).held == HeldRegeneration(
        next_hold_seq=3, artifact_definitions=(HeldItem(id="artifact-1", hold_seq=2),)
    )


async def test_record_reverted_overwrites_the_previous_record(subject: StoreUnderTest) -> None:
    first = RevertedDelivery(delivered_commit=DELIVERED_COMMIT, new_head=RECORDED_COMMIT, detected_at=NOW)
    second = RevertedDelivery(
        delivered_commit=RECORDED_COMMIT, new_head=SOURCE_COMMIT, detected_at=NOW + timedelta(hours=1)
    )

    async with subject.expect_transition(saved={REVERTED}):
        await subject.store.record_reverted(repository_id=subject.repository_id, reverted=first)
    async with subject.expect_transition(saved={REVERTED}):
        await subject.store.record_reverted(repository_id=subject.repository_id, reverted=second)

    assert (await subject.read()).reverted == second


async def test_pending_repository_ids_names_every_repository_with_a_status_other_than_none(
    db: InfrahubDatabase, subject: StoreUnderTest
) -> None:
    store = subject.store
    unused = await create_repository(db=db, branch=subject.branch, name="unused-repository")
    blocked = await create_repository(db=db, branch=subject.branch, name="blocked-repository")
    delivered = await create_repository(db=db, branch=subject.branch, name="delivered-repository")
    await _enqueue(subject, pending_merge("e1"))
    await store.enqueue(repository_id=blocked.id, entry=pending_merge("e2"), widen=False)
    await store.record_failure(repository_id=blocked.id, failure=REFUSED, final=True, retry_due_at=None)
    await store.enqueue(repository_id=delivered.id, entry=pending_merge("e3"), widen=False)
    snapshot = await store.start_attempt(repository_id=delivered.id)
    await store.settle_delivery(repository_id=delivered.id, snapshot=snapshot, delivered_commit=None)
    first_event = len(subject.timeline.events)

    pending = await store.pending_repository_ids()

    assert pending == frozenset({subject.repository_id, blocked.id})
    assert (await store.read(repository_id=unused.id)).status == RepositoryDeliveryStatus.NONE
    assert subject.timeline.events[first_event:] == []


async def test_references_source_branch_reads_the_queue_without_the_lock(subject: StoreUnderTest) -> None:
    await _enqueue(subject, pending_merge("e1", source_git_branch="feature-1"))
    first_event = len(subject.timeline.events)

    named = await subject.store.references_source_branch(repository_id=subject.repository_id, git_branch="feature-1")
    other = await subject.store.references_source_branch(repository_id=subject.repository_id, git_branch="feature-2")

    assert (named, other) == (True, False)
    assert subject.timeline.events[first_event:] == []


async def test_state_lock_has_its_time_to_live(subject: StoreUnderTest) -> None:
    await _enqueue(subject, pending_merge("e1"))

    lock = subject.lock_registry.get_existing(name=subject.repository_id, namespace=STATE_LOCK_NAMESPACE)

    assert lock is not None
    assert lock.ttl == STATE_LOCK_TTL_SECONDS == 30


async def test_timed_out_acquire_raises_and_writes_nothing(subject: StoreUnderTest) -> None:
    lock = subject.lock_registry.get(
        name=subject.repository_id, namespace=STATE_LOCK_NAMESPACE, ttl=STATE_LOCK_TTL_SECONDS
    )
    held = asyncio.Event()
    release = asyncio.Event()

    async def hold_the_lock() -> None:
        async with lock:
            held.set()
            await release.wait()

    holder = asyncio.create_task(hold_the_lock())
    await held.wait()
    try:
        with pytest.raises(
            DeliveryStateUnavailableError,
            match=(
                rf"^The lock of the delivery state of repository {re.escape(subject.repository_id)} "
                r"was not acquired within 10 seconds\.$"
            ),
        ):
            await subject.store.enqueue(repository_id=subject.repository_id, entry=pending_merge("e1"), widen=False)
    finally:
        release.set()
        await holder

    assert await subject.read() == _empty_intent(subject.repository_id)


async def test_queue_of_two_hundred_entries_keeps_its_order_and_settles_in_one_save(subject: StoreUnderTest) -> None:
    entries = tuple(pending_merge(f"entry-{number:03d}") for number in range(200))
    await _enqueue(subject, *entries)

    snapshot = await subject.store.start_attempt(repository_id=subject.repository_id)
    assert snapshot.queue == DeliveryQueue(version=200, entries=entries)

    async with subject.expect_transition(saved={STATUS, QUEUE}):
        lease = await subject.store.settle_delivery(
            repository_id=subject.repository_id, snapshot=snapshot, delivered_commit=None
        )

    assert lease is None
    intent = await subject.read()
    assert intent.status == RepositoryDeliveryStatus.NONE
    assert intent.queue == DeliveryQueue(
        version=201, removed_entry_ids=tuple(f"entry-{number:03d}" for number in range(200))
    )
