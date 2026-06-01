from infrahub import lock
from infrahub.lock import GLOBAL_GRAPH_LOCK, GLOBAL_SCHEMA_LOCK, LOCAL_SCHEMA_LOCK
from tests.adapters.lock import LockTimeline, RecordingLockRegistry


async def test_records_acquire_and_release_order(recording_lock_timeline: LockTimeline) -> None:
    async with lock.registry.get(name="repo-a", namespace="repository"):
        pass
    async with lock.registry.get(name="repo-b", namespace="repository"):
        pass

    assert recording_lock_timeline.acquire_sequence() == ["repository.repo-a", "repository.repo-b"]
    assert [event.action for event in recording_lock_timeline.events] == ["acquire", "release", "acquire", "release"]
    assert recording_lock_timeline.currently_held() == set()


async def test_held_at_checkpoint(recording_lock_timeline: LockTimeline) -> None:
    async with lock.registry.get(name="repo-a", namespace="repository"):
        recording_lock_timeline.checkpoint("inside")
    recording_lock_timeline.checkpoint("outside")

    recording_lock_timeline.assert_held_at_checkpoint("repository.repo-a", "inside", expected=True)
    recording_lock_timeline.assert_held_at_checkpoint("repository.repo-a", "outside", expected=False)


async def test_reentrant_acquire_records_single_boundary(recording_lock_timeline: LockTimeline) -> None:
    repo_lock = lock.registry.get(name="repo-a", namespace="repository")
    async with repo_lock:  # noqa: SIM117 - nesting is the re-entrant scenario under test
        async with repo_lock:
            recording_lock_timeline.checkpoint("nested")

    assert recording_lock_timeline.acquire_sequence() == ["repository.repo-a"]
    assert [event.action for event in recording_lock_timeline.events].count("release") == 1
    recording_lock_timeline.assert_held_at_checkpoint("repository.repo-a", "nested", expected=True)


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

    recording_lock_timeline.assert_never_overlap("repository.repo-a", "repository.repo-b")


async def test_fixture_swaps_registry_and_exposes_timeline(recording_lock_timeline: LockTimeline) -> None:
    assert isinstance(recording_lock_timeline, LockTimeline)
    assert isinstance(lock.registry, RecordingLockRegistry)
    assert lock.registry.timeline is recording_lock_timeline
