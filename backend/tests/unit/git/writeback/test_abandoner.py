from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import RepositoryDeliveryStatus
from infrahub.exceptions import (
    DatabaseError,
    DeliveryQueueChangedError,
    NothingPendingError,
    RepositoryConnectionError,
    ValidationError,
)
from infrahub.git.writeback.abandoner import WritebackAbandoner
from infrahub.git.writeback.models import (
    AbandonmentRecord,
    Actor,
    DeliveryAttemptResult,
    DeliveryOutcome,
    HeldItem,
    HeldRegeneration,
    PendingMerge,
    ReleaseLease,
)
from infrahub.git.writeback.ports import RepositoryRef
from infrahub.git.writeback.service import RepositoryWritebackService
from infrahub.lock import InfrahubLockRegistry
from tests.unit.git.writeback.fakes import (
    FixedClock,
    InMemoryDeliveryGit,
    InMemoryDeliveryState,
    RecordingRegenerationReleaser,
    Release,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping

    from infrahub.git.writeback.models import WritebackIntent
    from infrahub.lock import InfrahubLock

REPOSITORY = RepositoryRef(id="repository-1", name="net-repo", destination_git_branch="main")
NOW = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
LEASE_EXPIRY = datetime(2026, 10, 7, 12, 15, tzinfo=UTC)
ACTOR = Actor(account_id="account-1", account_name="admin")
RUN_LOGGER = "infrahub.tasks"

TRUNK = "a" * 40
"""The commit that Infrahub records before each test."""
FEATURE = "b" * 40
OTHER = "c" * 40


class WorkerStoppedError(BaseException):
    """Stops the abandonment where a crash of the worker would, so that nothing in the abandonment handles it."""


class LockProbe:
    """Records, for each observed step, whether the repository lock is held."""

    def __init__(self, *, lock: InfrahubLock) -> None:
        self.lock = lock
        self.observed: list[tuple[str, bool]] = []

    async def observe(self, *, step: str) -> None:
        self.observed.append((step, await self.lock.locked()))


class ProbedState(InMemoryDeliveryState):
    def __init__(self, *, clock: FixedClock, repository_names: Mapping[str, str], probe: LockProbe) -> None:
        super().__init__(clock=clock, repository_names=repository_names)
        self.probe = probe

    async def abandon(
        self, *, repository_id: str, queue_version: int, record: AbandonmentRecord, actor: Actor
    ) -> tuple[WritebackIntent, ReleaseLease | None]:
        await self.probe.observe(step="abandon")
        return await super().abandon(
            repository_id=repository_id, queue_version=queue_version, record=record, actor=actor
        )


class ProbedGit(InMemoryDeliveryGit):
    def __init__(self, *, destination_git_branch: str, head: str, probe: LockProbe) -> None:
        super().__init__(destination_git_branch=destination_git_branch, head=head)
        self.probe = probe

    async def notify_branch_deleted(self, *, git_branch: str) -> None:
        await self.probe.observe(step="notify")
        await super().notify_branch_deleted(git_branch=git_branch)


class SteppedReleaser(RecordingRegenerationReleaser):
    """Runs the action that a test sets before each release."""

    def __init__(self) -> None:
        super().__init__()
        self.before: Callable[[], Awaitable[None]] | None = None

    async def release(
        self, *, repository_id: str, held: HeldRegeneration, renew: Callable[[], Awaitable[None]]
    ) -> None:
        if self.before is not None:
            await self.before()
        await super().release(repository_id=repository_id, held=held, renew=renew)


@dataclass
class Rig:
    clock: FixedClock
    probe: LockProbe
    state: ProbedState
    git: ProbedGit
    releaser: SteppedReleaser
    abandoner: WritebackAbandoner
    service: RepositoryWritebackService

    @property
    def intent(self) -> WritebackIntent:
        return self.state.intents[REPOSITORY.id]

    async def queue(self, *entries: PendingMerge) -> None:
        for entry in entries:
            await self.state.enqueue(repository_id=REPOSITORY.id, entry=entry, widen=False)

    async def hold(self, *definition_ids: str) -> None:
        await self.state.hold(
            repository_id=REPOSITORY.id,
            held=HeldRegeneration(
                artifact_definitions=tuple(HeldItem(id=definition_id, hold_seq=0) for definition_id in definition_ids)
            ),
        )

    async def abandon(self, *, queue_version: int) -> AbandonmentRecord:
        return await self.abandoner.abandon(queue_version=queue_version, actor=ACTOR)

    async def deliver(self) -> DeliveryAttemptResult:
        return await self.service.deliver(final_attempt=True, manual=False, entry=None)

    def clear_calls(self) -> None:
        self.state.calls.clear()
        self.git.calls.clear()


def _merge(
    *,
    entry_id: str = "merge-1",
    source_branch: str = "add-vlan",
    source_git_branch: str = "feature",
    source_commit: str = FEATURE,
    delete_source_git_branch: bool = False,
) -> PendingMerge:
    return PendingMerge(
        entry_id=entry_id,
        source_branch=source_branch,
        source_git_branch=source_git_branch,
        source_commit=source_commit,
        merged_at=NOW,
        delete_source_git_branch=delete_source_git_branch,
    )


OTHER_MERGE = _merge(entry_id="merge-2", source_branch="add-vrf", source_git_branch="other", source_commit=OTHER)


def _held(*items: HeldItem) -> HeldRegeneration:
    return HeldRegeneration(artifact_definitions=items)


@pytest.fixture
def rig() -> Rig:
    clock = FixedClock(now=NOW)
    lock_registry = InfrahubLockRegistry(local_only=True)
    probe = LockProbe(lock=lock_registry.get(name=REPOSITORY.name, namespace="repository"))
    state = ProbedState(clock=clock, repository_names={REPOSITORY.id: REPOSITORY.name}, probe=probe)
    git = ProbedGit(destination_git_branch=REPOSITORY.destination_git_branch, head=TRUNK, probe=probe)
    releaser = SteppedReleaser()
    abandoner = WritebackAbandoner(
        repository=REPOSITORY, state=state, git=git, releaser=releaser, lock_registry=lock_registry, clock=clock
    )
    service = RepositoryWritebackService(
        repository=REPOSITORY, state=state, git=git, releaser=releaser, lock_registry=lock_registry, clock=clock
    )
    return Rig(clock=clock, probe=probe, state=state, git=git, releaser=releaser, abandoner=abandoner, service=service)


@dataclass
class RefusalCase:
    name: str
    queued: tuple[PendingMerge, ...]
    queue_version: int
    error: type[ValidationError]
    message: str


REFUSAL_CASES: list[RefusalCase] = [
    RefusalCase(
        name="stale_version",
        queued=(_merge(),),
        queue_version=0,
        error=DeliveryQueueChangedError,
        message=r"^The pending pushes of repository net-repo changed since version 0; reload and try again\.$",
    ),
    RefusalCase(
        name="empty_queue",
        queued=(),
        queue_version=0,
        error=NothingPendingError,
        message=r"^Repository net-repo has nothing pending to push\.$",
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in REFUSAL_CASES])
async def test_refusal_changes_nothing(rig: Rig, case: RefusalCase) -> None:
    await rig.queue(*case.queued)
    await rig.hold("definition-1")
    before = rig.intent
    rig.clear_calls()

    with pytest.raises(case.error, match=case.message):
        await rig.abandon(queue_version=case.queue_version)

    assert rig.intent == before
    assert rig.state.calls == ["abandon"]
    assert rig.git.calls == ["recorded_commit"]
    assert rig.releaser.releases == []


async def test_entries_leave_the_queue_and_the_lease_is_taken_before_the_release(rig: Rig) -> None:
    entry = _merge()
    await rig.queue(entry)
    await rig.hold("definition-1")
    rig.clear_calls()
    at_release: list[tuple[tuple[PendingMerge, ...], tuple[str, ...]]] = []

    async def read_state() -> None:
        at_release.append((rig.intent.queue.entries, tuple(lease.lease_id for lease in rig.intent.held.release_leases)))

    rig.releaser.before = read_state

    record = await rig.abandon(queue_version=1)

    expected = AbandonmentRecord(
        abandoned_at=NOW,
        account_id="account-1",
        account_name="admin",
        queue_version=1,
        recorded_commit=TRUNK,
        entries=(entry,),
    )
    assert record == expected
    assert rig.intent.last_abandonment == expected
    assert at_release == [((), ("lease-1",))]
    assert rig.intent.status == RepositoryDeliveryStatus.NONE
    assert rig.intent.queue.removed_entry_ids == ("merge-1",)
    assert rig.releaser.releases == [
        Release(repository_id=REPOSITORY.id, held=_held(HeldItem(id="definition-1", hold_seq=1)))
    ]
    assert rig.intent.held.artifact_definitions == ()
    assert rig.intent.held.release_leases == ()
    assert rig.state.calls == ["abandon", "renew_lease", "clear_released"]
    assert rig.git.calls == ["recorded_commit"]


async def test_abandonment_with_no_recorded_commit_records_an_empty_commit(rig: Rig) -> None:
    entry = _merge()
    await rig.queue(entry)
    rig.git.graph_commit = None

    record = await rig.abandon(queue_version=1)

    assert record == AbandonmentRecord(
        abandoned_at=NOW,
        account_id="account-1",
        account_name="admin",
        queue_version=1,
        recorded_commit="",
        entries=(entry,),
    )
    assert rig.intent.queue.entries == ()


async def test_branch_deletion_is_broadcast_for_flagged_entries_only(rig: Rig) -> None:
    await rig.queue(_merge(delete_source_git_branch=True), OTHER_MERGE)

    await rig.abandon(queue_version=2)

    assert rig.git.notified_branches == ["feature"]
    assert rig.git.deleted_branches == []


async def test_failed_broadcast_still_releases(rig: Rig, caplog: pytest.LogCaptureFixture) -> None:
    await rig.queue(
        _merge(delete_source_git_branch=True),
        _merge(entry_id="merge-2", source_git_branch="other", source_commit=OTHER, delete_source_git_branch=True),
    )
    await rig.hold("definition-1")
    rig.git.failures["notify_branch_deleted"] = [RepositoryConnectionError(identifier="net-repo")]

    with caplog.at_level(logging.WARNING, logger=RUN_LOGGER):
        await rig.abandon(queue_version=2)

    assert [record.getMessage() for record in caplog.records if record.levelno == logging.WARNING] == [
        "Failed to tell the workers that the branch feature of repository net-repo is gone."
    ]
    assert rig.git.notified_branches == ["other"]
    assert rig.releaser.releases == [
        Release(repository_id=REPOSITORY.id, held=_held(HeldItem(id="definition-1", hold_seq=1)))
    ]


async def test_release_runs_after_the_lock_is_released(rig: Rig) -> None:
    await rig.queue(_merge(delete_source_git_branch=True))
    await rig.hold("definition-1")

    async def observe_the_release() -> None:
        await rig.probe.observe(step="release")

    rig.releaser.before = observe_the_release

    await rig.abandon(queue_version=1)

    assert rig.probe.observed == [("abandon", True), ("notify", True), ("release", False)]


async def test_clear_keeps_a_hold_made_during_the_release(rig: Rig) -> None:
    await rig.queue(_merge())
    await rig.hold("definition-1")

    async def merge_and_hold_again() -> None:
        await rig.queue(OTHER_MERGE)
        await rig.hold("definition-1")

    rig.releaser.before = merge_and_hold_again

    await rig.abandon(queue_version=1)

    assert rig.releaser.releases == [
        Release(repository_id=REPOSITORY.id, held=_held(HeldItem(id="definition-1", hold_seq=1)))
    ]
    assert rig.intent.held.artifact_definitions == (HeldItem(id="definition-1", hold_seq=2),)
    assert rig.intent.held.release_leases == ()
    assert rig.intent.queue.entries == (OTHER_MERGE,)


async def test_crash_before_the_clear_leaves_a_lease_that_a_held_only_run_releases_once_expired(rig: Rig) -> None:
    await rig.queue(_merge())
    await rig.hold("definition-1")
    rig.releaser.failures.append(WorkerStoppedError())

    with pytest.raises(WorkerStoppedError):
        await rig.abandon(queue_version=1)

    held = HeldItem(id="definition-1", hold_seq=1)
    assert rig.intent.queue.entries == ()
    assert rig.intent.held.artifact_definitions == (held,)
    assert rig.intent.held.release_leases == (
        ReleaseLease(lease_id="lease-1", expires_at=LEASE_EXPIRY, artifact_definitions=(held,)),
    )
    assert await rig.deliver() == DeliveryAttemptResult(outcome=DeliveryOutcome.NOTHING_PENDING)
    assert rig.releaser.releases == []

    rig.clock.advance(seconds=15 * 60)
    result = await rig.deliver()

    assert result == DeliveryAttemptResult(outcome=DeliveryOutcome.RELEASED)
    assert rig.releaser.releases == [Release(repository_id=REPOSITORY.id, held=_held(held))]
    assert rig.intent.held.artifact_definitions == ()
    assert rig.intent.held.release_leases == ()


async def test_failed_release_expires_the_lease_now_and_keeps_the_items_held(rig: Rig) -> None:
    entry = _merge()
    await rig.queue(entry)
    await rig.hold("definition-1")
    rig.releaser.failures.append(RuntimeError("dispatch failed"))
    rig.clear_calls()

    with pytest.raises(RuntimeError, match=r"^dispatch failed$"):
        await rig.abandon(queue_version=1)

    held = HeldItem(id="definition-1", hold_seq=1)
    assert rig.state.calls == ["abandon", "expire_lease"]
    assert rig.intent.queue.entries == ()
    assert rig.intent.last_abandonment is not None
    assert rig.intent.last_abandonment.entries == (entry,)
    assert rig.intent.held.artifact_definitions == (held,)
    assert rig.intent.held.release_leases == (
        ReleaseLease(lease_id="lease-1", expires_at=NOW, artifact_definitions=(held,)),
    )

    assert await rig.deliver() == DeliveryAttemptResult(outcome=DeliveryOutcome.RELEASED)
    assert rig.releaser.releases == [Release(repository_id=REPOSITORY.id, held=_held(held))]


async def test_failed_expiry_keeps_the_error_of_the_release(rig: Rig) -> None:
    await rig.queue(_merge())
    await rig.hold("definition-1")
    rig.releaser.failures.append(RuntimeError("dispatch failed"))
    rig.state.failures["expire_lease"] = [DatabaseError(message="database is down")]

    with pytest.raises(RuntimeError, match=r"^dispatch failed$"):
        await rig.abandon(queue_version=1)

    held = HeldItem(id="definition-1", hold_seq=1)
    assert rig.intent.held.release_leases == (
        ReleaseLease(lease_id="lease-1", expires_at=LEASE_EXPIRY, artifact_definitions=(held,)),
    )
