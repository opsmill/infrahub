from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.exceptions import RepositoryError
from infrahub.git.models import GitReadOnlyRepositoryCheckRefs, TrackedRef
from infrahub.git.refs_check.checker import ReadOnlyRepositoryRefsChecker, RefNameValidator, RefsCheckScheduler
from infrahub.git.refs_check.models import (
    RefHeads,
    RefMovement,
    RefsCheckCycleSummary,
    RefsCheckOutcome,
    RefsCheckResult,
)
from infrahub.git.state.cache_keys import (
    REFS_CHECK_ANNOUNCED_TTL_SECONDS,
    refs_check_announced_key,
    refs_check_due_key,
    refs_check_last_key,
    refs_check_running_key,
)
from infrahub.message_bus import InfrahubMessage, messages
from tests.adapters.cache import ClaimAwareCache
from tests.adapters.lock import LockTimeline, RecordingLockRegistry
from tests.adapters.message_bus import BusRecorder

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.message_bus.types import MessageTTL

REPOSITORY_ID = "1f2e3d4c-5b6a-4978-8765-4321abcdef00"
REPOSITORY_NAME = "readonly-repo"
LOCATION = "https://example.com/readonly-repo.git"
IMPORTED_COMMIT = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
LOCAL_HEAD = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
REMOTE_HEAD = "cccccccccccccccccccccccccccccccccccccccc"
RETRY_SECONDS = 300
ANNOUNCED_KEY = refs_check_announced_key(REPOSITORY_ID, branch_name="main")


class RecordingRefsGateway:
    """Answers with scripted heads, marking the remote listing and the fetch on the lock timeline."""

    def __init__(
        self,
        *,
        timeline: LockTimeline,
        local_heads: dict[str, str | None],
        remote_heads: dict[str, str | None],
        remote_error: Exception | None = None,
    ) -> None:
        self.timeline = timeline
        self.local_heads = local_heads
        self.remote_heads = remote_heads
        self.remote_error = remote_error
        self.listings: list[list[str]] = []
        self.fetches: list[str] = []

    async def read_heads(self, model: GitReadOnlyRepositoryCheckRefs, refs: Sequence[str]) -> tuple[RefHeads, ...]:
        self.timeline.checkpoint("ls-remote")
        self.listings.append(list(refs))
        if self.remote_error is not None:
            raise self.remote_error
        return tuple(
            RefHeads(ref=ref, local_head=self.local_heads.get(ref), remote_head=self.remote_heads.get(ref))
            for ref in refs
        )

    async def fetch(self, model: GitReadOnlyRepositoryCheckRefs) -> None:
        self.timeline.checkpoint("fetch")
        self.fetches.append(model.repository_name)


class HangingRefsGateway:
    """Never answers the remote, the way an unresponsive host with no transport timeout would."""

    def __init__(self, *, timeline: LockTimeline) -> None:
        self.timeline = timeline
        self.fetches: list[str] = []

    async def read_heads(self, model: GitReadOnlyRepositoryCheckRefs, refs: Sequence[str]) -> tuple[RefHeads, ...]:
        await asyncio.sleep(30)
        return tuple(RefHeads(ref=ref, local_head=LOCAL_HEAD, remote_head=REMOTE_HEAD) for ref in refs)

    async def fetch(self, model: GitReadOnlyRepositoryCheckRefs) -> None:
        self.timeline.checkpoint("fetch")
        self.fetches.append(model.repository_name)


class CheckpointingBusRecorder(BusRecorder):
    """Marks each publish on the shared lock timeline, so the lock held at that point is assertable."""

    def __init__(self, timeline: LockTimeline) -> None:
        super().__init__()
        self.timeline = timeline

    async def publish(
        self, message: InfrahubMessage, routing_key: str, delay: MessageTTL | None = None, is_retry: bool = False
    ) -> None:
        self.timeline.checkpoint("broadcast")
        await super().publish(message=message, routing_key=routing_key, delay=delay, is_retry=is_retry)


class CheckTimeFailingCache(ClaimAwareCache):
    """Fails only the check-time write, the way a cache blip during that one call would."""

    async def set(self, key: str, value: str, expires: int | None = None, not_exists: bool = False) -> bool | None:
        if key == refs_check_last_key(REPOSITORY_ID):
            raise ConnectionError("cache unreachable")
        return await super().set(key=key, value=value, expires=expires, not_exists=not_exists)


class ClaimReleaseFailingCache(ClaimAwareCache):
    """Fails only the claim release, the way a cache blip during that one call would."""

    async def delete(self, key: str) -> None:
        if key == refs_check_running_key(REPOSITORY_ID):
            raise ConnectionError("cache unreachable")
        await super().delete(key=key)


class AnnouncedWriteFailingCache(ClaimAwareCache):
    """Fails only the announced-head write, the way a cache blip during that one call would."""

    async def set(self, key: str, value: str, expires: int | None = None, not_exists: bool = False) -> bool | None:
        if key == ANNOUNCED_KEY:
            raise ConnectionError("cache unreachable")
        return await super().set(key=key, value=value, expires=expires, not_exists=not_exists)


class AnnouncedWriteOrderCache(ClaimAwareCache):
    """Records how many broadcasts had been published at each announced-head write."""

    def __init__(self, bus: BusRecorder) -> None:
        super().__init__()
        self.bus = bus
        self.broadcasts_at_write: list[tuple[str, int]] = []

    async def set(self, key: str, value: str, expires: int | None = None, not_exists: bool = False) -> bool | None:
        if key.startswith(refs_check_announced_key(REPOSITORY_ID, branch_name="")):
            self.broadcasts_at_write.append((key, len(self.bus.messages)))
        return await super().set(key=key, value=value, expires=expires, not_exists=not_exists)


class PublishFailingBus(BusRecorder):
    """Fails every publish, the way a broker outage during the broadcast would."""

    async def publish(
        self, message: InfrahubMessage, routing_key: str, delay: MessageTTL | None = None, is_retry: bool = False
    ) -> None:
        raise ConnectionError("broker unreachable")


class CrashingRefsGateway:
    async def read_heads(self, model: GitReadOnlyRepositoryCheckRefs, refs: Sequence[str]) -> tuple[RefHeads, ...]:
        raise RuntimeError("the worker died mid-check")

    async def fetch(self, model: GitReadOnlyRepositoryCheckRefs) -> None:
        raise RuntimeError("the worker died mid-check")


class RecordingTrackedCommitReader:
    """Answers with the commit each branch has imported, recording every branch it was asked about."""

    def __init__(self, commits: dict[str, str | None] | None = None) -> None:
        self.commits = {"main": IMPORTED_COMMIT} if commits is None else commits
        self.reads: list[str] = []

    async def read(self, *, repository_id: str, branch_name: str) -> str | None:
        self.reads.append(branch_name)
        return self.commits.get(branch_name)


class SequencedTrackedCommitReader:
    """Answers each read with the next scripted commit, the way an import landing between two reads would."""

    def __init__(self, answers: list[str | None]) -> None:
        self.answers = answers
        self.reads: list[str] = []

    async def read(self, *, repository_id: str, branch_name: str) -> str | None:
        self.reads.append(branch_name)
        return self.answers.pop(0)


class HangingTrackedCommitReader:
    """Never answers, the way a graph read stalled behind a slow database would."""

    async def read(self, *, repository_id: str, branch_name: str) -> str | None:
        await asyncio.sleep(30)
        return IMPORTED_COMMIT


def build_model(
    *,
    repository_id: str = REPOSITORY_ID,
    repository_name: str = REPOSITORY_NAME,
    refs: list[TrackedRef] | None = None,
) -> GitReadOnlyRepositoryCheckRefs:
    return GitReadOnlyRepositoryCheckRefs(
        repository_id=repository_id,
        repository_name=repository_name,
        location=LOCATION,
        refs=refs or [TrackedRef(infrahub_branch_name="main", infrahub_branch_id="main-branch-id", ref="stable")],
    )


def build_checker(
    *,
    cache: ClaimAwareCache,
    bus: BusRecorder,
    timeline: LockTimeline,
    gateway: RecordingRefsGateway | CrashingRefsGateway,
    tracked_commit_reader: RecordingTrackedCommitReader | SequencedTrackedCommitReader | None = None,
) -> ReadOnlyRepositoryRefsChecker:
    return ReadOnlyRepositoryRefsChecker(
        cache=cache,
        message_bus=bus,
        lock_registry=RecordingLockRegistry(timeline=timeline),
        gateway=gateway,
        ref_validator=RefNameValidator(check_ref_format=lambda _: True),
        scheduler=build_scheduler(cache),
        tracked_commit_reader=tracked_commit_reader or RecordingTrackedCommitReader(),
        claim_ttl_seconds=180,
        detect_timeout_seconds=30,
    )


def build_scheduler(cache: ClaimAwareCache) -> RefsCheckScheduler:
    return RefsCheckScheduler(cache=cache, interval_seconds=900, retry_seconds=RETRY_SECONDS)


async def test_only_repositories_that_are_due_are_selected() -> None:
    cache = ClaimAwareCache()
    scheduler = RefsCheckScheduler(cache=cache, interval_seconds=900, retry_seconds=RETRY_SECONDS)
    first = build_model()
    second = build_model(repository_id="second-id", repository_name="second-repo")

    assert await scheduler.select_due([first, second]) == [first, second]
    assert await scheduler.select_due([first, second]) == []


async def test_the_due_key_carries_the_configured_interval_as_its_ttl() -> None:
    cache = ClaimAwareCache()
    model = build_model()

    await RefsCheckScheduler(cache=cache, interval_seconds=1800, retry_seconds=RETRY_SECONDS).select_due([model])

    assert cache.expires[refs_check_due_key(REPOSITORY_ID)] == 1800


async def test_an_unchanged_remote_lists_refs_and_transfers_nothing() -> None:
    timeline = LockTimeline()
    bus = BusRecorder()
    gateway = RecordingRefsGateway(
        timeline=timeline, local_heads={"stable": IMPORTED_COMMIT}, remote_heads={"stable": IMPORTED_COMMIT}
    )
    checker = build_checker(cache=ClaimAwareCache(), bus=bus, timeline=timeline, gateway=gateway)

    result = await checker.check(build_model(), run_id="run-1")

    assert gateway.listings == [["stable"]]
    assert gateway.fetches == []
    assert bus.messages == []
    assert result.movements == ()
    assert result.outcome is RefsCheckOutcome.COMPLETED
    assert timeline.acquire_sequence(prefix=f"repository.{REPOSITORY_NAME}") == []


async def test_a_worker_already_at_the_remote_head_still_announces_a_move_the_pool_was_not_told_about() -> None:
    """Another worker fetched on its own, so this copy agrees with the remote while the rest of the pool may not."""
    timeline = LockTimeline()
    bus = BusRecorder()
    cache = ClaimAwareCache()
    gateway = RecordingRefsGateway(
        timeline=timeline, local_heads={"stable": REMOTE_HEAD}, remote_heads={"stable": REMOTE_HEAD}
    )
    checker = build_checker(cache=cache, bus=bus, timeline=timeline, gateway=gateway)

    result = await checker.check(build_model(), run_id="run-1")

    assert result.movements == (
        RefMovement(ref="stable", infrahub_branch_name="main", previous_head=IMPORTED_COMMIT, new_head=REMOTE_HEAD),
    )
    assert gateway.fetches == []
    assert [(message.infrahub_branch_name, message.commit) for message in bus.messages] == [("main", IMPORTED_COMMIT)]
    assert cache.storage[ANNOUNCED_KEY] == REMOTE_HEAD
    assert cache.expires[ANNOUNCED_KEY] == REFS_CHECK_ANNOUNCED_TTL_SECONDS


async def test_a_worker_behind_a_move_already_announced_fetches_without_announcing_it_again() -> None:
    timeline = LockTimeline()
    bus = BusRecorder()
    cache = ClaimAwareCache()
    await cache.set(key=ANNOUNCED_KEY, value=REMOTE_HEAD)
    gateway = RecordingRefsGateway(
        timeline=timeline, local_heads={"stable": LOCAL_HEAD}, remote_heads={"stable": REMOTE_HEAD}
    )
    reader = RecordingTrackedCommitReader()
    checker = build_checker(cache=cache, bus=bus, timeline=timeline, gateway=gateway, tracked_commit_reader=reader)

    result = await checker.check(build_model(), run_id="run-1")

    assert result.movements == ()
    assert gateway.fetches == [REPOSITORY_NAME]
    assert bus.messages == []
    # The announced head answered the question, so the graph was never asked.
    assert reader.reads == []


async def test_a_stale_announced_head_is_announced_even_when_the_import_caught_up_with_the_remote() -> None:
    """An import records the head only after its own broadcast, so a stale value means that broadcast never went out."""
    timeline = LockTimeline()
    bus = BusRecorder()
    cache = ClaimAwareCache()
    await cache.set(key=ANNOUNCED_KEY, value=LOCAL_HEAD)
    gateway = RecordingRefsGateway(
        timeline=timeline, local_heads={"stable": REMOTE_HEAD}, remote_heads={"stable": REMOTE_HEAD}
    )
    reader = RecordingTrackedCommitReader({"main": REMOTE_HEAD})
    checker = build_checker(cache=cache, bus=bus, timeline=timeline, gateway=gateway, tracked_commit_reader=reader)

    result = await checker.check(build_model(), run_id="run-1")

    assert result.movements == (
        RefMovement(ref="stable", infrahub_branch_name="main", previous_head=LOCAL_HEAD, new_head=REMOTE_HEAD),
    )
    assert [message.commit for message in bus.messages] == [REMOTE_HEAD]
    assert cache.storage[ANNOUNCED_KEY] == REMOTE_HEAD
    # The stored value answered the question, so the graph was read only to pin the broadcast.
    assert reader.reads == ["main"]


async def test_a_cold_cache_remembers_the_imported_commit_when_the_remote_is_still_on_it() -> None:
    """With nothing cached the imported commit is the baseline, so a fresh instance announces nothing."""
    timeline = LockTimeline()
    bus = BusRecorder()
    cache = ClaimAwareCache()
    gateway = RecordingRefsGateway(
        timeline=timeline, local_heads={"stable": IMPORTED_COMMIT}, remote_heads={"stable": IMPORTED_COMMIT}
    )
    reader = RecordingTrackedCommitReader()
    checker = build_checker(cache=cache, bus=bus, timeline=timeline, gateway=gateway, tracked_commit_reader=reader)

    await checker.check(build_model(), run_id="run-1")
    await checker.check(build_model(), run_id="run-2")

    assert bus.messages == []
    assert cache.storage[ANNOUNCED_KEY] == IMPORTED_COMMIT
    # Written back on the first check, so the second one does not read the graph again.
    assert reader.reads == ["main"]


async def test_a_cold_cache_announces_a_remote_ahead_of_the_imported_commit_once() -> None:
    """The remote moved while nothing was cached, which is a move the pool has not been told about."""
    timeline = LockTimeline()
    bus = BusRecorder()
    cache = ClaimAwareCache()
    gateway = RecordingRefsGateway(
        timeline=timeline, local_heads={"stable": REMOTE_HEAD}, remote_heads={"stable": REMOTE_HEAD}
    )
    checker = build_checker(cache=cache, bus=bus, timeline=timeline, gateway=gateway)

    first = await checker.check(build_model(), run_id="run-1")
    second = await checker.check(build_model(), run_id="run-2")

    assert [movement.previous_head for movement in first.movements] == [IMPORTED_COMMIT]
    assert second.movements == ()
    assert [message.commit for message in bus.messages] == [IMPORTED_COMMIT]


async def test_a_failed_broadcast_leaves_the_move_unannounced_so_the_next_check_retries_it() -> None:
    timeline = LockTimeline()
    cache = ClaimAwareCache()
    gateway = RecordingRefsGateway(
        timeline=timeline, local_heads={"stable": LOCAL_HEAD}, remote_heads={"stable": REMOTE_HEAD}
    )
    failing = build_checker(cache=cache, bus=PublishFailingBus(), timeline=timeline, gateway=gateway)

    with pytest.raises(ConnectionError, match=r"^broker unreachable$"):
        await failing.check(build_model(), run_id="run-1")

    assert ANNOUNCED_KEY not in cache.storage

    # The fetch has already happened, so this worker's copy agrees with the remote from here on.
    gateway.local_heads["stable"] = REMOTE_HEAD
    bus = BusRecorder()
    retrying = build_checker(cache=cache, bus=bus, timeline=timeline, gateway=gateway)

    result = await retrying.check(build_model(), run_id="run-2")

    assert [movement.new_head for movement in result.movements] == [REMOTE_HEAD]
    assert [message.commit for message in bus.messages] == [IMPORTED_COMMIT]
    assert cache.storage[ANNOUNCED_KEY] == REMOTE_HEAD


async def test_each_announced_head_is_written_only_after_its_own_broadcast() -> None:
    timeline = LockTimeline()
    bus = BusRecorder()
    cache = AnnouncedWriteOrderCache(bus=bus)
    gateway = RecordingRefsGateway(
        timeline=timeline, local_heads={"stable": LOCAL_HEAD}, remote_heads={"stable": REMOTE_HEAD}
    )
    model = build_model(
        refs=[
            TrackedRef(infrahub_branch_name="main", infrahub_branch_id="main-branch-id", ref="stable"),
            TrackedRef(infrahub_branch_name="feature", infrahub_branch_id="feature-branch-id", ref="stable"),
        ]
    )
    reader = RecordingTrackedCommitReader({"main": IMPORTED_COMMIT, "feature": IMPORTED_COMMIT})
    checker = build_checker(cache=cache, bus=bus, timeline=timeline, gateway=gateway, tracked_commit_reader=reader)

    await checker.check(model, run_id="run-1")

    assert cache.broadcasts_at_write == [
        (ANNOUNCED_KEY, 1),
        (refs_check_announced_key(REPOSITORY_ID, branch_name="feature"), 2),
    ]


async def test_a_failed_announced_head_write_costs_one_repeated_broadcast_and_not_the_result() -> None:
    timeline = LockTimeline()
    bus = BusRecorder()
    cache = AnnouncedWriteFailingCache()
    gateway = RecordingRefsGateway(
        timeline=timeline, local_heads={"stable": REMOTE_HEAD}, remote_heads={"stable": REMOTE_HEAD}
    )
    checker = build_checker(cache=cache, bus=bus, timeline=timeline, gateway=gateway)

    first = await checker.check(build_model(), run_id="run-1")
    second = await checker.check(build_model(), run_id="run-2")

    assert first.outcome is RefsCheckOutcome.COMPLETED
    assert [movement.new_head for movement in first.movements] == [REMOTE_HEAD]
    assert [movement.new_head for movement in second.movements] == [REMOTE_HEAD]
    assert [message.commit for message in bus.messages] == [IMPORTED_COMMIT, IMPORTED_COMMIT]
    assert refs_check_running_key(REPOSITORY_ID) not in cache.storage


async def test_the_repository_lock_covers_the_fetch_and_the_broadcast_but_never_the_listing() -> None:
    timeline = LockTimeline()
    bus = CheckpointingBusRecorder(timeline=timeline)
    gateway = RecordingRefsGateway(
        timeline=timeline, local_heads={"stable": LOCAL_HEAD}, remote_heads={"stable": REMOTE_HEAD}
    )
    checker = build_checker(cache=ClaimAwareCache(), bus=bus, timeline=timeline, gateway=gateway)

    await checker.check(build_model(), run_id="run-1")

    timeline.assert_not_held_at_checkpoint(f"repository.{REPOSITORY_NAME}", "ls-remote")
    timeline.assert_held_at_checkpoint(f"repository.{REPOSITORY_NAME}", "fetch")
    # The broadcast has to be inside the lock too: it names the commit the fetch just made
    # reachable, and a reader between the two would see neither.
    timeline.assert_held_at_checkpoint(f"repository.{REPOSITORY_NAME}", "broadcast")


async def test_a_moved_ref_is_broadcast_once_per_branch_pinned_to_the_imported_commit() -> None:
    timeline = LockTimeline()
    bus = BusRecorder()
    gateway = RecordingRefsGateway(
        timeline=timeline,
        local_heads={"stable": LOCAL_HEAD, "untouched": IMPORTED_COMMIT},
        remote_heads={"stable": REMOTE_HEAD, "untouched": IMPORTED_COMMIT},
    )
    other_branch_commit = "dddddddddddddddddddddddddddddddddddddddd"
    model = build_model(
        refs=[
            TrackedRef(infrahub_branch_name="main", infrahub_branch_id="main-branch-id", ref="stable"),
            TrackedRef(infrahub_branch_name="feature", infrahub_branch_id="feature-branch-id", ref="stable"),
            TrackedRef(infrahub_branch_name="quiet", infrahub_branch_id="quiet-branch-id", ref="untouched"),
        ]
    )
    reader = RecordingTrackedCommitReader(
        {"main": IMPORTED_COMMIT, "feature": other_branch_commit, "quiet": IMPORTED_COMMIT}
    )
    checker = build_checker(
        cache=ClaimAwareCache(), bus=bus, timeline=timeline, gateway=gateway, tracked_commit_reader=reader
    )

    result = await checker.check(model, run_id="run-1")

    # Two branches on one ref each carry their own baseline, so each is reported against it.
    assert result.movements == (
        RefMovement(ref="stable", infrahub_branch_name="main", previous_head=IMPORTED_COMMIT, new_head=REMOTE_HEAD),
        RefMovement(
            ref="stable", infrahub_branch_name="feature", previous_head=other_branch_commit, new_head=REMOTE_HEAD
        ),
    )

    broadcast = [message for message in bus.messages if isinstance(message, messages.RefreshGitFetch)]
    assert [(message.infrahub_branch_name, message.commit) for message in broadcast] == [
        ("main", IMPORTED_COMMIT),
        ("feature", other_branch_commit),
    ]
    assert {message.repository_kind for message in broadcast} == {InfrahubKind.READONLYREPOSITORY}
    # Every branch is read once for its baseline, and only the moved ones again under the lock.
    assert reader.reads == ["main", "feature", "quiet", "main", "feature"]


async def test_a_branch_with_nothing_imported_yet_is_fetched_but_not_broadcast() -> None:
    """There is no commit to pin such a branch to, and an unpinned broadcast would move the pool."""
    timeline = LockTimeline()
    bus = BusRecorder()
    gateway = RecordingRefsGateway(
        timeline=timeline, local_heads={"stable": LOCAL_HEAD}, remote_heads={"stable": REMOTE_HEAD}
    )
    model = build_model(
        refs=[
            TrackedRef(infrahub_branch_name="main", infrahub_branch_id="main-branch-id", ref="stable"),
            TrackedRef(infrahub_branch_name="never-imported", infrahub_branch_id="never-imported-id", ref="stable"),
        ]
    )
    checker = build_checker(
        cache=ClaimAwareCache(),
        bus=bus,
        timeline=timeline,
        gateway=gateway,
        tracked_commit_reader=RecordingTrackedCommitReader({"main": IMPORTED_COMMIT, "never-imported": None}),
    )

    result = await checker.check(model, run_id="run-1")

    assert [movement.infrahub_branch_name for movement in result.movements] == ["main"]
    assert gateway.fetches == [REPOSITORY_NAME]
    assert [message.infrahub_branch_name for message in bus.messages] == ["main"]


async def test_the_broadcast_pins_the_commit_read_while_the_lock_is_held() -> None:
    """The broadcast pins whatever commit is imported when the lock is held, not an earlier one."""
    timeline = LockTimeline()
    bus = BusRecorder()
    gateway = RecordingRefsGateway(
        timeline=timeline, local_heads={"stable": LOCAL_HEAD}, remote_heads={"stable": REMOTE_HEAD}
    )
    imported_meanwhile = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    reader = SequencedTrackedCommitReader([IMPORTED_COMMIT, imported_meanwhile])
    checker = build_checker(
        cache=ClaimAwareCache(), bus=bus, timeline=timeline, gateway=gateway, tracked_commit_reader=reader
    )

    await checker.check(build_model(), run_id="run-1")

    assert [message.commit for message in bus.messages] == [imported_meanwhile]
    assert reader.reads == ["main", "main"]


async def test_a_branch_whose_repository_vanished_before_the_lock_is_not_broadcast() -> None:
    timeline = LockTimeline()
    bus = BusRecorder()
    cache = ClaimAwareCache()
    gateway = RecordingRefsGateway(
        timeline=timeline, local_heads={"stable": LOCAL_HEAD}, remote_heads={"stable": REMOTE_HEAD}
    )
    checker = build_checker(
        cache=cache,
        bus=bus,
        timeline=timeline,
        gateway=gateway,
        tracked_commit_reader=SequencedTrackedCommitReader([IMPORTED_COMMIT, None]),
    )

    result = await checker.check(build_model(), run_id="run-1")

    assert [movement.ref for movement in result.movements] == ["stable"]
    assert gateway.fetches == [REPOSITORY_NAME]
    assert bus.messages == []
    # Nothing was broadcast, so nothing may be recorded as announced.
    assert ANNOUNCED_KEY not in cache.storage


async def test_every_distinct_tracked_ref_is_read_in_one_listing() -> None:
    """Two branches following one ref cost one listing, and two refs still cost one between them."""
    timeline = LockTimeline()
    gateway = RecordingRefsGateway(
        timeline=timeline,
        local_heads={"stable": LOCAL_HEAD, "release": LOCAL_HEAD},
        remote_heads={"stable": LOCAL_HEAD, "release": LOCAL_HEAD},
    )
    model = build_model(
        refs=[
            TrackedRef(infrahub_branch_name="main", infrahub_branch_id="main-branch-id", ref="stable"),
            TrackedRef(infrahub_branch_name="feature", infrahub_branch_id="feature-branch-id", ref="stable"),
            TrackedRef(infrahub_branch_name="other", infrahub_branch_id="other-branch-id", ref="release"),
        ]
    )
    checker = build_checker(cache=ClaimAwareCache(), bus=BusRecorder(), timeline=timeline, gateway=gateway)

    await checker.check(model, run_id="run-1")

    assert gateway.listings == [["stable", "release"]]


async def test_a_second_trigger_while_one_is_in_flight_reports_the_claim_and_contacts_nothing() -> None:
    cache = ClaimAwareCache()
    timeline = LockTimeline()
    bus = BusRecorder()
    gateway = RecordingRefsGateway(
        timeline=timeline, local_heads={"stable": LOCAL_HEAD}, remote_heads={"stable": REMOTE_HEAD}
    )
    await cache.set(key=refs_check_running_key(REPOSITORY_ID), value="run-already-running", expires=180)
    checker = build_checker(cache=cache, bus=bus, timeline=timeline, gateway=gateway)

    result = await checker.check(build_model(), run_id="run-2")

    assert result.outcome is RefsCheckOutcome.SKIPPED_CLAIMED
    assert result.claimed_by == "run-already-running"
    assert gateway.listings == []
    assert gateway.fetches == []
    assert bus.messages == []
    assert cache.storage[refs_check_running_key(REPOSITORY_ID)] == "run-already-running"


async def test_a_check_that_outlived_its_claim_leaves_the_later_run_s_claim_alone() -> None:
    """Convergence is unbounded, so a slow check can finish after its own claim has expired.

    Deleting whatever is under the key at that point would strip the protection from the run that
    has since taken it, which is the overlap the claim exists to prevent.
    """
    cache = ClaimAwareCache()
    timeline = LockTimeline()
    gateway = RecordingRefsGateway(
        timeline=timeline, local_heads={"stable": IMPORTED_COMMIT}, remote_heads={"stable": IMPORTED_COMMIT}
    )
    checker = build_checker(cache=cache, bus=BusRecorder(), timeline=timeline, gateway=gateway)
    model = build_model()

    # Stand in for the claim expiring mid-run and a later run taking it.
    async def take_over(_model: GitReadOnlyRepositoryCheckRefs, refs: Sequence[str]) -> tuple[RefHeads, ...]:
        await cache.set(key=refs_check_running_key(REPOSITORY_ID), value="run-2")
        return tuple(RefHeads(ref=ref, local_head=IMPORTED_COMMIT, remote_head=IMPORTED_COMMIT) for ref in refs)

    gateway.read_heads = take_over  # type: ignore[method-assign]

    await checker.check(model, run_id="run-1")

    assert cache.storage[refs_check_running_key(REPOSITORY_ID)] == "run-2"


async def test_a_crashed_run_releases_its_in_flight_key() -> None:
    cache = ClaimAwareCache()
    timeline = LockTimeline()
    checker = build_checker(cache=cache, bus=BusRecorder(), timeline=timeline, gateway=CrashingRefsGateway())

    with pytest.raises(RuntimeError, match=r"^the worker died mid-check$"):
        await checker.check(build_model(), run_id="run-1")

    assert refs_check_running_key(REPOSITORY_ID) not in cache.storage


async def test_an_unreachable_remote_is_recorded_and_made_due_again() -> None:
    cache = ClaimAwareCache()
    timeline = LockTimeline()
    bus = BusRecorder()
    await RefsCheckScheduler(cache=cache, interval_seconds=900, retry_seconds=RETRY_SECONDS).select_due([build_model()])
    gateway = RecordingRefsGateway(
        timeline=timeline,
        local_heads={"stable": LOCAL_HEAD},
        remote_heads={},
        remote_error=RepositoryError(identifier=REPOSITORY_NAME, message="fatal: unable to access remote"),
    )
    checker = build_checker(cache=cache, bus=bus, timeline=timeline, gateway=gateway)

    result = await checker.check(build_model(), run_id="run-1")

    assert result.failed is True
    assert result.repository_name == REPOSITORY_NAME
    assert "unable to access remote" in (result.failure_reason or "")
    # Due again sooner than a whole interval, but not on the very next tick: a repository whose
    # remote is permanently gone would otherwise take a concurrency slot every minute forever.
    assert cache.expires[refs_check_due_key(REPOSITORY_ID)] == RETRY_SECONDS
    assert refs_check_running_key(REPOSITORY_ID) not in cache.storage
    assert timeline.currently_held() == set()
    assert bus.messages == []


async def test_a_repository_made_due_again_is_passed_over_until_the_backoff_expires() -> None:
    cache = ClaimAwareCache()
    timeline = LockTimeline()
    scheduler = build_scheduler(cache)
    gateway = RecordingRefsGateway(
        timeline=timeline,
        local_heads={"stable": LOCAL_HEAD},
        remote_heads={},
        remote_error=RepositoryError(identifier=REPOSITORY_NAME, message="fatal: unable to access remote"),
    )
    checker = build_checker(cache=cache, bus=BusRecorder(), timeline=timeline, gateway=gateway)
    model = build_model()
    await scheduler.select_due([model])

    await checker.check(model, run_id="run-1")

    assert await scheduler.select_due([model]) == []


async def test_the_check_time_is_written_on_success_and_on_failure_alike() -> None:
    timeline = LockTimeline()
    quiet_cache = ClaimAwareCache()
    quiet = build_checker(
        cache=quiet_cache,
        bus=BusRecorder(),
        timeline=timeline,
        gateway=RecordingRefsGateway(
            timeline=timeline, local_heads={"stable": IMPORTED_COMMIT}, remote_heads={"stable": IMPORTED_COMMIT}
        ),
    )
    failing_cache = ClaimAwareCache()
    failing = build_checker(
        cache=failing_cache,
        bus=BusRecorder(),
        timeline=timeline,
        gateway=RecordingRefsGateway(
            timeline=timeline,
            local_heads={"stable": LOCAL_HEAD},
            remote_heads={},
            remote_error=RepositoryError(identifier=REPOSITORY_NAME, message="fatal: unable to access remote"),
        ),
    )

    await quiet.check(build_model(), run_id="run-1")
    await failing.check(build_model(), run_id="run-2")

    assert refs_check_last_key(REPOSITORY_ID) in quiet_cache.storage
    assert refs_check_last_key(REPOSITORY_ID) in failing_cache.storage


async def test_a_failed_check_time_write_does_not_cost_the_claim_or_the_result() -> None:
    """The check time is best effort; the claim release and the outcome are not.

    A cache that fails this one write must not leave the repository claimed, which would suppress
    every check of it until the claim expires.
    """
    cache = CheckTimeFailingCache()
    timeline = LockTimeline()
    bus = BusRecorder()
    gateway = RecordingRefsGateway(
        timeline=timeline, local_heads={"stable": IMPORTED_COMMIT}, remote_heads={"stable": IMPORTED_COMMIT}
    )
    checker = build_checker(cache=cache, bus=bus, timeline=timeline, gateway=gateway)

    result = await checker.check(build_model(), run_id="run-1")

    assert result.movements == ()
    assert result.failure_reason is None
    assert refs_check_running_key(REPOSITORY_ID) not in cache.storage


async def test_a_failed_check_time_write_does_not_replace_the_reason_the_check_failed() -> None:
    cache = CheckTimeFailingCache()
    timeline = LockTimeline()
    gateway = RecordingRefsGateway(
        timeline=timeline,
        local_heads={"stable": LOCAL_HEAD},
        remote_heads={},
        remote_error=RepositoryError(identifier=REPOSITORY_NAME, message="fatal: unable to access remote"),
    )
    checker = build_checker(cache=cache, bus=BusRecorder(), timeline=timeline, gateway=gateway)

    result = await checker.check(build_model(), run_id="run-1")

    assert result.failed is True
    assert "unable to access remote" in (result.failure_reason or "")
    assert "cache unreachable" not in (result.failure_reason or "")
    assert refs_check_running_key(REPOSITORY_ID) not in cache.storage


async def test_a_failed_claim_release_does_not_cost_the_result_of_the_check_it_ends() -> None:
    """The claim expires on its own, so a release that could not happen costs one interval.

    Letting it raise out of the ``finally`` would instead discard the outcome of a check that has
    already listed the remote and converged the pool, and have the cycle retry all of it.
    """
    timeline = LockTimeline()
    bus = BusRecorder()
    gateway = RecordingRefsGateway(
        timeline=timeline, local_heads={"stable": LOCAL_HEAD}, remote_heads={"stable": REMOTE_HEAD}
    )
    checker = build_checker(cache=ClaimReleaseFailingCache(), bus=bus, timeline=timeline, gateway=gateway)

    result = await checker.check(build_model(), run_id="run-1")

    assert result.outcome is RefsCheckOutcome.COMPLETED
    assert [movement.ref for movement in result.movements] == ["stable"]
    assert [message.commit for message in bus.messages] == [IMPORTED_COMMIT]


async def test_a_check_asked_for_by_hand_does_not_start_spacing_the_scheduled_ones() -> None:
    """Only the schedule writes the due key, so a failure outside it must not invent one.

    A repository checked on demand is not being spaced by the schedule; writing a due key here
    would suppress the scheduled checks that follow a manual one that happened to fail.
    """
    cache = ClaimAwareCache()
    timeline = LockTimeline()
    gateway = RecordingRefsGateway(
        timeline=timeline,
        local_heads={"stable": LOCAL_HEAD},
        remote_heads={},
        remote_error=RepositoryError(identifier=REPOSITORY_NAME, message="fatal: unable to access remote"),
    )
    checker = build_checker(cache=cache, bus=BusRecorder(), timeline=timeline, gateway=gateway)
    model = build_model()

    result = await checker.check(model, run_id="run-1")

    assert result.failed is True
    assert refs_check_due_key(REPOSITORY_ID) not in cache.storage
    assert await build_scheduler(cache).select_due([model]) == [model]


async def test_an_unexpected_programming_error_is_not_recorded_as_a_repository_failure() -> None:
    """A bug must surface as a crash, not as a per-cycle "this remote failed" that never stops."""
    cache = ClaimAwareCache()
    timeline = LockTimeline()
    gateway = RecordingRefsGateway(
        timeline=timeline,
        local_heads={"stable": LOCAL_HEAD},
        remote_heads={},
        remote_error=ValueError("badly formed hexadecimal UUID string"),
    )
    checker = build_checker(cache=cache, bus=BusRecorder(), timeline=timeline, gateway=gateway)

    with pytest.raises(ValueError, match=r"^badly formed hexadecimal UUID string$"):
        await checker.check(build_model(), run_id="run-1")

    assert refs_check_running_key(REPOSITORY_ID) not in cache.storage


async def test_an_unresponsive_remote_is_abandoned_without_taking_the_repository_lock() -> None:
    """The wall-clock bound sits on the listing and the planning, the steps that can wait on a remote or the graph.

    It deliberately does not wrap the convergence: that holds the repository lock, and this lock
    carries no expiry, so cancelling a run part-way through releasing it would leave every later
    import of that repository blocked for good.
    """
    cache = ClaimAwareCache()
    timeline = LockTimeline()
    bus = BusRecorder()
    gateway = HangingRefsGateway(timeline=timeline)
    checker = ReadOnlyRepositoryRefsChecker(
        cache=cache,
        message_bus=bus,
        lock_registry=RecordingLockRegistry(timeline=timeline),
        gateway=gateway,
        ref_validator=RefNameValidator(check_ref_format=lambda _: True),
        scheduler=build_scheduler(cache),
        tracked_commit_reader=RecordingTrackedCommitReader(),
        claim_ttl_seconds=180,
        detect_timeout_seconds=0.05,
    )
    await build_scheduler(cache).select_due([build_model()])

    result = await checker.check(build_model(), run_id="run-1")

    assert result.failed is True
    assert result.failure_reason == "Timed out after 0.05s checking the remote refs."
    assert gateway.fetches == []
    assert bus.messages == []
    assert timeline.acquire_sequence(prefix=f"repository.{REPOSITORY_NAME}") == []
    assert refs_check_running_key(REPOSITORY_ID) not in cache.storage
    assert cache.expires[refs_check_due_key(REPOSITORY_ID)] == RETRY_SECONDS


async def test_a_slow_baseline_read_is_abandoned_before_the_claim_can_lapse() -> None:
    """The baseline reads share the listing's bound, so a slow graph cannot outlast the claim's lease."""
    cache = ClaimAwareCache()
    timeline = LockTimeline()
    bus = BusRecorder()
    gateway = RecordingRefsGateway(
        timeline=timeline, local_heads={"stable": LOCAL_HEAD}, remote_heads={"stable": REMOTE_HEAD}
    )
    checker = ReadOnlyRepositoryRefsChecker(
        cache=cache,
        message_bus=bus,
        lock_registry=RecordingLockRegistry(timeline=timeline),
        gateway=gateway,
        ref_validator=RefNameValidator(check_ref_format=lambda _: True),
        scheduler=build_scheduler(cache),
        tracked_commit_reader=HangingTrackedCommitReader(),
        claim_ttl_seconds=180,
        detect_timeout_seconds=0.05,
    )

    result = await checker.check(build_model(), run_id="run-1")

    assert result.failure_reason == "Timed out after 0.05s checking the remote refs."
    assert gateway.fetches == []
    assert bus.messages == []
    assert timeline.acquire_sequence(prefix=f"repository.{REPOSITORY_NAME}") == []
    assert refs_check_running_key(REPOSITORY_ID) not in cache.storage


async def test_the_cycle_record_counts_each_repository_by_what_happened_to_it() -> None:
    summary = RefsCheckCycleSummary(
        results=(
            RefsCheckResult(
                repository_id="a",
                repository_name="quiet",
                outcome=RefsCheckOutcome.COMPLETED,
                contacted_remote=True,
            ),
            RefsCheckResult(
                repository_id="b",
                repository_name="moved",
                outcome=RefsCheckOutcome.COMPLETED,
                movements=(
                    RefMovement(
                        ref="stable", infrahub_branch_name="main", previous_head=IMPORTED_COMMIT, new_head=REMOTE_HEAD
                    ),
                ),
                contacted_remote=True,
            ),
            RefsCheckResult(
                repository_id="c",
                repository_name="broken",
                outcome=RefsCheckOutcome.FAILED,
                failure_reason="unreachable",
                contacted_remote=True,
            ),
            RefsCheckResult(
                repository_id="d",
                repository_name="already-running",
                outcome=RefsCheckOutcome.SKIPPED_CLAIMED,
                claimed_by="another-run",
            ),
        ),
        not_due=4,
        duration_seconds=1.5,
    )

    # A repository held by another run was not checked by this cycle, and is counted apart from
    # the ones that were never due.
    assert (
        summary.checked_count,
        summary.moved_count,
        summary.failed_count,
        summary.claimed_elsewhere_count,
        summary.not_due,
    ) == (3, 1, 1, 1, 4)


@dataclass
class InvalidResultCase:
    name: str
    kwargs: dict[str, object]
    expected_message: str


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(
            InvalidResultCase(
                name="a_skipped_check_cannot_carry_movements",
                kwargs={
                    "outcome": RefsCheckOutcome.SKIPPED_CLAIMED,
                    "claimed_by": "another-run",
                    "movements": (
                        RefMovement(
                            ref="stable",
                            infrahub_branch_name="main",
                            previous_head=IMPORTED_COMMIT,
                            new_head=REMOTE_HEAD,
                        ),
                    ),
                },
                expected_message="^A skipped_claimed check cannot carry movements$",
            ),
            id="a_skipped_check_cannot_carry_movements",
        ),
        pytest.param(
            InvalidResultCase(
                name="a_completed_check_cannot_carry_a_failure_reason",
                kwargs={"outcome": RefsCheckOutcome.COMPLETED, "failure_reason": "unreachable"},
                expected_message="^A completed check must carry a failure reason if and only if it failed$",
            ),
            id="a_completed_check_cannot_carry_a_failure_reason",
        ),
        pytest.param(
            InvalidResultCase(
                name="a_failed_check_must_carry_a_failure_reason",
                kwargs={"outcome": RefsCheckOutcome.FAILED},
                expected_message="^A failed check must carry a failure reason if and only if it failed$",
            ),
            id="a_failed_check_must_carry_a_failure_reason",
        ),
        pytest.param(
            InvalidResultCase(
                name="a_completed_check_cannot_name_a_claim_holder",
                kwargs={"outcome": RefsCheckOutcome.COMPLETED, "claimed_by": "another-run"},
                expected_message="^A completed check cannot name the run that holds the claim$",
            ),
            id="a_completed_check_cannot_name_a_claim_holder",
        ),
        pytest.param(
            InvalidResultCase(
                name="a_check_that_lost_the_claim_cannot_have_contacted_the_remote",
                kwargs={
                    "outcome": RefsCheckOutcome.SKIPPED_CLAIMED,
                    "claimed_by": "another-run",
                    "contacted_remote": True,
                },
                expected_message="^A check that never got the claim cannot have contacted the remote$",
            ),
            id="a_check_that_lost_the_claim_cannot_have_contacted_the_remote",
        ),
    ],
)
async def test_a_result_cannot_describe_two_outcomes_at_once(case: InvalidResultCase) -> None:
    with pytest.raises(ValueError, match=case.expected_message):
        RefsCheckResult(repository_id="a", repository_name="repo", **case.kwargs)  # type: ignore[arg-type]


async def test_an_invalid_ref_is_refused_before_the_remote_is_contacted() -> None:
    cache = ClaimAwareCache()
    timeline = LockTimeline()
    gateway = RecordingRefsGateway(timeline=timeline, local_heads={}, remote_heads={})
    checker = ReadOnlyRepositoryRefsChecker(
        cache=cache,
        message_bus=BusRecorder(),
        lock_registry=RecordingLockRegistry(timeline=timeline),
        gateway=gateway,
        ref_validator=RefNameValidator(check_ref_format=lambda _: False),
        scheduler=build_scheduler(cache),
        tracked_commit_reader=RecordingTrackedCommitReader(),
        claim_ttl_seconds=180,
        detect_timeout_seconds=30,
    )

    result = await checker.check(build_model(), run_id="run-1")

    assert result.failure_reason == "Refusing to check the invalid ref 'stable'."
    assert gateway.listings == []
    # It never asked the remote anything, so the cycle must not count it among the ones it checked.
    assert result.contacted_remote is False
    assert RefsCheckCycleSummary(results=(result,), not_due=0, duration_seconds=0.0).checked_count == 0
