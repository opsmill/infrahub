from infrahub import config, lock
from infrahub.lock import (
    GLOBAL_GRAPH_LOCK,
    GLOBAL_INIT_LOCK,
    GLOBAL_SCHEMA_LOCK,
    GLOBAL_TASKMGR_INIT_LOCK,
    LOCAL_SCHEMA_LOCK,
)
from tests.adapters.lock import LockAction, LockTimeline, RecordingLockRegistry


async def test_records_acquire_and_release_order(recording_lock_timeline: LockTimeline) -> None:
    async with lock.registry.get(name="repo-a", namespace="repository"):
        pass
    async with lock.registry.get(name="repo-b", namespace="repository"):
        pass

    assert recording_lock_timeline.acquire_sequence() == ["repository.repo-a", "repository.repo-b"]
    assert [event.action for event in recording_lock_timeline.events] == [
        LockAction.ACQUIRE,
        LockAction.RELEASE,
        LockAction.ACQUIRE,
        LockAction.RELEASE,
    ]
    assert recording_lock_timeline.currently_held() == set()


async def test_held_at_checkpoint(recording_lock_timeline: LockTimeline) -> None:
    async with lock.registry.get(name="repo-a", namespace="repository"):
        recording_lock_timeline.checkpoint("inside")
    recording_lock_timeline.checkpoint("outside")

    recording_lock_timeline.assert_held_at_checkpoint("repository.repo-a", "inside")
    recording_lock_timeline.assert_not_held_at_checkpoint("repository.repo-a", "outside")


async def test_reentrant_acquire_records_single_boundary(recording_lock_timeline: LockTimeline) -> None:
    repo_lock = lock.registry.get(name="repo-a", namespace="repository")
    async with repo_lock:  # noqa: SIM117 - nesting is the re-entrant scenario under test
        async with repo_lock:
            recording_lock_timeline.checkpoint("nested")

    assert recording_lock_timeline.acquire_sequence() == ["repository.repo-a"]
    assert [event.action for event in recording_lock_timeline.events].count(LockAction.RELEASE) == 1
    recording_lock_timeline.assert_held_at_checkpoint("repository.repo-a", "nested")


async def test_multi_lock_records_each_member(recording_lock_timeline: LockTimeline) -> None:
    async with lock.registry.global_graph_lock():
        held = recording_lock_timeline.currently_held()

    assert held == {LOCAL_SCHEMA_LOCK, GLOBAL_GRAPH_LOCK, GLOBAL_SCHEMA_LOCK}
    assert recording_lock_timeline.currently_held() == set()


async def test_assert_never_overlap(recording_lock_timeline: LockTimeline) -> None:
    async with lock.registry.get(name="repo-a", namespace="repository"):
        pass
    async with lock.registry.get(name="repo-b", namespace="repository"):
        pass

    recording_lock_timeline.assert_never_overlap(["repository.repo-a", "repository.repo-b"])


async def test_fixture_swaps_registry_and_exposes_timeline(recording_lock_timeline: LockTimeline) -> None:
    assert isinstance(recording_lock_timeline, LockTimeline)
    assert isinstance(lock.registry, RecordingLockRegistry)
    assert lock.registry.timeline is recording_lock_timeline


async def test_recording_registry_applies_init_lock_ttl(recording_lock_timeline: LockTimeline) -> None:
    # The recording registry must resolve TTLs the same way production does, otherwise init locks
    # would silently behave differently under test than they do at runtime.
    expected_ttl = config.SETTINGS.cache.init_lock_ttl_mins * 60

    assert lock.registry.get(name=GLOBAL_INIT_LOCK).ttl == expected_ttl
    assert lock.registry.get(name=GLOBAL_TASKMGR_INIT_LOCK).ttl == expected_ttl
    assert lock.registry.get(name="repo-a", namespace="repository").ttl is None
