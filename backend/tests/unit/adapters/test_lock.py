from infrahub import lock
from tests.adapters.lock import LockTimeline, install_recording_lock_registry


async def test_records_acquire_and_release_order() -> None:
    timeline = install_recording_lock_registry()

    async with lock.registry.get(name="repo-a", namespace="repository"):
        pass
    async with lock.registry.get(name="repo-b", namespace="repository"):
        pass

    assert timeline.acquire_sequence() == ["repository.repo-a", "repository.repo-b"]
    assert [event.action for event in timeline.events] == ["acquire", "release", "acquire", "release"]
    assert timeline.currently_held() == set()


async def test_held_at_checkpoint() -> None:
    timeline = install_recording_lock_registry()

    async with lock.registry.get(name="repo-a", namespace="repository"):
        timeline.checkpoint("inside")
    timeline.checkpoint("outside")

    timeline.assert_held_at_checkpoint("repository.repo-a", "inside", expected=True)
    timeline.assert_held_at_checkpoint("repository.repo-a", "outside", expected=False)


async def test_reentrant_acquire_records_single_boundary() -> None:
    timeline = install_recording_lock_registry()

    repo_lock = lock.registry.get(name="repo-a", namespace="repository")
    async with repo_lock:  # noqa: SIM117 - nesting is the re-entrant scenario under test
        async with repo_lock:
            timeline.checkpoint("nested")

    assert timeline.acquire_sequence() == ["repository.repo-a"]
    assert [event.action for event in timeline.events].count("release") == 1
    timeline.assert_held_at_checkpoint("repository.repo-a", "nested", expected=True)


async def test_multi_lock_records_each_member() -> None:
    timeline = install_recording_lock_registry()

    async with lock.registry.global_graph_lock():
        held = timeline.currently_held()

    assert held == {"local.schema", "global.graph", "global.schema"}
    assert timeline.currently_held() == set()


async def test_assert_never_overlap() -> None:
    timeline = install_recording_lock_registry()

    async with lock.registry.get(name="repo-a", namespace="repository"):
        pass
    async with lock.registry.get(name="repo-b", namespace="repository"):
        pass

    timeline.assert_never_overlap("repository.repo-a", "repository.repo-b")


async def test_install_returns_timeline_and_swaps_registry() -> None:
    timeline = install_recording_lock_registry()
    assert isinstance(timeline, LockTimeline)
    assert lock.registry.timeline is timeline
