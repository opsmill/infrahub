from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from infrahub.git.activity.models import (
    RepositoryActivityBranchOutcome,
    RepositoryActivityOperation,
    RepositoryActivityPhase,
)
from infrahub.git.activity.recorder import ActiveRunNotFoundError, ActiveRuns, RepositoryActivity
from infrahub.git.state.cache_keys import (
    ACTIVITY_LAST_RUN_TTL_SECONDS,
    ACTIVITY_RUN_RENEW_SECONDS,
    ACTIVITY_RUN_TTL_SECONDS,
)
from tests.adapters.cache import CacheSetCall, RecordingCache, UnreachableCache

if TYPE_CHECKING:
    from infrahub.message_bus.types import KVTTL
    from infrahub.services.adapters.cache import InfrahubCache

REPOSITORY_ID = "18d39e83-1ef7-d650-5424-0242ac120005"
LAST_SYNC_KEY = f"git:activity:last:{REPOSITORY_ID}:sync"
STARTED_AT = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
WAIT_SECONDS = 5


class FakeClock:
    def __init__(self) -> None:
        self.now = STARTED_AT

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)


class ManualSleep:
    """A sleep that returns only when the test lets the interval pass."""

    def __init__(self) -> None:
        self.intervals: list[float] = []
        self._sleepers: asyncio.Queue[asyncio.Future[None]] = asyncio.Queue()

    async def __call__(self, seconds: float) -> None:
        self.intervals.append(seconds)
        sleeper: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        await self._sleepers.put(sleeper)
        await sleeper

    async def elapse(self) -> None:
        """End the current sleep and wait until the sleeper has done its work and sleeps again."""
        sleeper = await asyncio.wait_for(self._sleepers.get(), timeout=WAIT_SECONDS)
        sleeper.set_result(None)
        next_sleeper = await asyncio.wait_for(self._sleepers.get(), timeout=WAIT_SECONDS)
        await self._sleepers.put(next_sleeper)

    def pending(self) -> list[asyncio.Future[None]]:
        """Return the sleeps that started and were not ended by the test."""
        sleepers = []
        while not self._sleepers.empty():
            sleepers.append(self._sleepers.get_nowait())
        return sleepers


class LastRunBlockingCache(RecordingCache):
    """Holds every last-run write until the test releases it, and signals each delete."""

    def __init__(self) -> None:
        super().__init__()
        self.last_run_write_started = asyncio.Event()
        self.release_last_run_write = asyncio.Event()
        self.deleted_a_key = asyncio.Event()

    async def set(
        self, key: str, value: str, expires: KVTTL | int | None = None, not_exists: bool = False
    ) -> bool | None:
        if key.startswith("git:activity:last:"):
            self.last_run_write_started.set()
            await asyncio.wait_for(self.release_last_run_write.wait(), timeout=WAIT_SECONDS)
        return await super().set(key=key, value=value, expires=expires, not_exists=not_exists)

    async def delete(self, key: str) -> None:
        await super().delete(key=key)
        self.deleted_a_key.set()


def build_activity(
    cache: InfrahubCache, clock: FakeClock, sleep: ManualSleep, active_runs: ActiveRuns | None = None
) -> RepositoryActivity:
    return RepositoryActivity(
        cache=cache,
        active_runs=active_runs or ActiveRuns(),
        worker_id="worker-1",
        now=clock,
        sleep=sleep,
        run_ttl_seconds=ACTIVITY_RUN_TTL_SECONDS,
        renew_interval_seconds=ACTIVITY_RUN_RENEW_SECONDS,
        last_run_ttl_seconds=ACTIVITY_LAST_RUN_TTL_SECONDS,
    )


def run_key(run_id: str) -> str:
    return f"git:activity:run:{REPOSITORY_ID}:{run_id}"


async def test_a_started_run_is_written_with_a_300_second_lifetime() -> None:
    cache = RecordingCache()
    activity = build_activity(cache=cache, clock=FakeClock(), sleep=ManualSleep())

    async with activity.track(repository_id=REPOSITORY_ID, operation=RepositoryActivityOperation.SYNC) as run:
        assert cache.set_calls == [
            CacheSetCall(
                key=run_key(run.run_id),
                value=json.dumps(
                    {
                        "run_id": run.run_id,
                        "repository_id": REPOSITORY_ID,
                        "operation": "sync",
                        "phase": None,
                        "branch_name": None,
                        "worker_id": "worker-1",
                        "started_at": "2026-01-01T10:00:00Z",
                        "updated_at": "2026-01-01T10:00:00Z",
                    },
                    separators=(",", ":"),
                ),
                expires=300,
                not_exists=False,
            )
        ]


async def test_a_phase_change_is_written_at_once() -> None:
    cache = RecordingCache()
    clock = FakeClock()
    activity = build_activity(cache=cache, clock=clock, sleep=ManualSleep())

    async with activity.track(repository_id=REPOSITORY_ID, operation=RepositoryActivityOperation.SYNC) as run:
        clock.advance(seconds=5)
        await run.set_phase(phase=RepositoryActivityPhase.BUILDING, branch_name="branch1")

        written = json.loads(cache.storage[run_key(run.run_id)])
        assert (written["phase"], written["branch_name"], written["updated_at"]) == (
            "building",
            "branch1",
            "2026-01-01T10:00:05Z",
        )
        assert cache.set_calls[-1].expires == 300


async def test_the_record_is_renewed_every_60_seconds_while_the_run_is_active() -> None:
    cache = RecordingCache()
    clock = FakeClock()
    sleep = ManualSleep()
    activity = build_activity(cache=cache, clock=clock, sleep=sleep)

    async with activity.track(repository_id=REPOSITORY_ID, operation=RepositoryActivityOperation.SYNC) as run:
        await run.set_phase(phase=RepositoryActivityPhase.FETCHING)
        clock.advance(seconds=60)
        await sleep.elapse()

        renewed = json.loads(cache.storage[run_key(run.run_id)])
        assert (renewed["phase"], renewed["updated_at"]) == ("fetching", "2026-01-01T10:01:00Z")
        assert [call.expires for call in cache.set_calls] == [300, 300, 300]
        assert sleep.intervals == [60, 60]


async def test_a_run_that_succeeds_replaces_its_record_with_the_last_run() -> None:
    cache = RecordingCache()
    clock = FakeClock()
    activity = build_activity(cache=cache, clock=clock, sleep=ManualSleep())

    async with activity.track(repository_id=REPOSITORY_ID, operation=RepositoryActivityOperation.SYNC) as run:
        run.record_branch(branch_name="main", outcome=RepositoryActivityBranchOutcome.IMPORTED)
        clock.advance(seconds=30)

    assert run_key(run.run_id) in cache.deleted
    assert list(cache.storage) == [LAST_SYNC_KEY]
    assert json.loads(cache.storage[LAST_SYNC_KEY]) == {
        "operation": "sync",
        "started_at": "2026-01-01T10:00:00Z",
        "finished_at": "2026-01-01T10:00:30Z",
        "branches": [{"branch_name": "main", "outcome": "imported"}],
    }
    assert cache.expires[LAST_SYNC_KEY] == 30 * 24 * 60 * 60


async def test_a_run_that_fails_replaces_its_record_and_the_failure_propagates() -> None:
    cache = RecordingCache()
    activity = build_activity(cache=cache, clock=FakeClock(), sleep=ManualSleep())

    with pytest.raises(RuntimeError, match=r"^import broke$"):
        async with activity.track(repository_id=REPOSITORY_ID, operation=RepositoryActivityOperation.SYNC) as run:
            raise RuntimeError("import broke")

    assert run_key(run.run_id) in cache.deleted
    assert list(cache.storage) == [LAST_SYNC_KEY]


async def test_a_cancelled_run_replaces_its_record_and_stays_cancelled() -> None:
    cache = RecordingCache()
    activity = build_activity(cache=cache, clock=FakeClock(), sleep=ManualSleep())
    started = asyncio.Event()
    run_ids: list[str] = []

    async def body() -> None:
        async with activity.track(repository_id=REPOSITORY_ID, operation=RepositoryActivityOperation.SYNC) as run:
            run_ids.append(run.run_id)
            started.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(body())
    await asyncio.wait_for(started.wait(), timeout=WAIT_SECONDS)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=WAIT_SECONDS)

    assert cache.deleted == [run_key(run_ids[0])]
    assert list(cache.storage) == [LAST_SYNC_KEY]


async def test_a_run_cancelled_again_during_its_cleanup_still_finishes_the_cleanup() -> None:
    """A cancel scope cancels at every await, so the cleanup must not depend on the caller staying alive."""
    cache = LastRunBlockingCache()
    active_runs = ActiveRuns()
    activity = build_activity(cache=cache, clock=FakeClock(), sleep=ManualSleep(), active_runs=active_runs)
    started = asyncio.Event()
    run_ids: list[str] = []

    async def body() -> None:
        async with activity.track(repository_id=REPOSITORY_ID, operation=RepositoryActivityOperation.SYNC) as run:
            run_ids.append(run.run_id)
            started.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(body())
    await asyncio.wait_for(started.wait(), timeout=WAIT_SECONDS)
    task.cancel()
    await asyncio.wait_for(cache.last_run_write_started.wait(), timeout=WAIT_SECONDS)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=WAIT_SECONDS)
    cache.release_last_run_write.set()
    await asyncio.wait_for(cache.deleted_a_key.wait(), timeout=WAIT_SECONDS)

    assert cache.deleted == [run_key(run_ids[0])]
    assert list(cache.storage) == [LAST_SYNC_KEY]
    with pytest.raises(ActiveRunNotFoundError, match=rf"^No active repository run {run_ids[0]} in this process$"):
        active_runs.get(run_id=run_ids[0])


async def test_the_renewal_is_stopped_when_the_run_ends() -> None:
    sleep = ManualSleep()
    activity = build_activity(cache=RecordingCache(), clock=FakeClock(), sleep=sleep)

    async with activity.track(repository_id=REPOSITORY_ID, operation=RepositoryActivityOperation.SYNC):
        await sleep.elapse()

    assert [sleeper.cancelled() for sleeper in sleep.pending()] == [True]


async def test_the_last_run_lists_each_branch_once_with_its_last_outcome() -> None:
    cache = RecordingCache()
    activity = build_activity(cache=cache, clock=FakeClock(), sleep=ManualSleep())

    async with activity.track(repository_id=REPOSITORY_ID, operation=RepositoryActivityOperation.SYNC) as run:
        run.record_branch(branch_name="imported", outcome=RepositoryActivityBranchOutcome.IMPORTED)
        run.record_branch(branch_name="retried", outcome=RepositoryActivityBranchOutcome.FAILED)
        run.record_branch(branch_name="retried", outcome=RepositoryActivityBranchOutcome.IMPORTED)
        run.record_branch(branch_name="failed-later", outcome=RepositoryActivityBranchOutcome.IMPORTED)
        run.record_branch(branch_name="failed-later", outcome=RepositoryActivityBranchOutcome.FAILED)

    assert json.loads(cache.storage[LAST_SYNC_KEY])["branches"] == [
        {"branch_name": "imported", "outcome": "imported"},
        {"branch_name": "retried", "outcome": "imported"},
        {"branch_name": "failed-later", "outcome": "failed"},
    ]


async def test_each_operation_keeps_its_own_last_run() -> None:
    cache = RecordingCache()
    activity = build_activity(cache=cache, clock=FakeClock(), sleep=ManualSleep())

    async with activity.track(repository_id=REPOSITORY_ID, operation=RepositoryActivityOperation.ADD):
        pass
    async with activity.track(repository_id=REPOSITORY_ID, operation=RepositoryActivityOperation.SYNC):
        pass

    assert sorted(cache.storage) == [f"git:activity:last:{REPOSITORY_ID}:add", LAST_SYNC_KEY]


async def test_a_run_that_keeps_the_last_run_leaves_the_earlier_one_in_place() -> None:
    cache = RecordingCache()
    clock = FakeClock()
    activity = build_activity(cache=cache, clock=clock, sleep=ManualSleep())

    async with activity.track(repository_id=REPOSITORY_ID, operation=RepositoryActivityOperation.SYNC) as run:
        run.record_branch(branch_name="main", outcome=RepositoryActivityBranchOutcome.FAILED)
    earlier = cache.storage[LAST_SYNC_KEY]
    clock.advance(seconds=30)
    async with activity.track(repository_id=REPOSITORY_ID, operation=RepositoryActivityOperation.SYNC) as kept:
        kept.keep_last_run()

    assert run_key(kept.run_id) in cache.deleted
    assert list(cache.storage) == [LAST_SYNC_KEY]
    assert cache.storage[LAST_SYNC_KEY] == earlier
    assert json.loads(earlier)["branches"] == [{"branch_name": "main", "outcome": "failed"}]


async def test_an_unreachable_cache_does_not_fail_the_run() -> None:
    sleep = ManualSleep()
    activity = build_activity(cache=UnreachableCache(), clock=FakeClock(), sleep=sleep)
    steps: list[str] = []

    async with activity.track(repository_id=REPOSITORY_ID, operation=RepositoryActivityOperation.SYNC) as run:
        await run.set_phase(phase=RepositoryActivityPhase.FETCHING)
        await sleep.elapse()
        run.record_branch(branch_name="main", outcome=RepositoryActivityBranchOutcome.IMPORTED)
        steps.append("body finished")

    assert steps == ["body finished"]


async def test_an_active_run_is_found_by_its_id_only_until_it_ends() -> None:
    active_runs = ActiveRuns()
    activity = build_activity(cache=RecordingCache(), clock=FakeClock(), sleep=ManualSleep(), active_runs=active_runs)

    async with activity.track(repository_id=REPOSITORY_ID, operation=RepositoryActivityOperation.SYNC) as run:
        assert active_runs.get(run_id=run.run_id) is run

    with pytest.raises(ActiveRunNotFoundError, match=rf"^No active repository run {run.run_id} in this process$"):
        active_runs.get(run_id=run.run_id)
