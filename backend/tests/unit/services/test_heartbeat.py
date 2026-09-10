from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Callable

import pytest

from infrahub.components import ComponentType
from infrahub.services.heartbeat import WorkerHeartbeat
from infrahub.worker import WORKER_IDENTITY
from tests.adapters.cache import MemoryCache
from tests.adapters.log import FakeLogger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from infrahub.message_bus.types import KVTTL

ACTIVE_KEY = f"workers:active:git_agent:worker:{WORKER_IDENTITY}"
WORKER_KEY = f"workers:worker:{WORKER_IDENTITY}"
BEAT_INTERVAL = 0.05


class RecordingCache(MemoryCache):
    """A memory cache that records when the heartbeat key is written and whether it was closed."""

    def __init__(self, failures_before_success: int = 0, fail_after_sets: int | None = None) -> None:
        super().__init__()
        self.beat_times: list[float] = []
        self.closed = False
        self.failures_before_success = failures_before_success
        self.fail_after_sets = fail_after_sets
        self.set_count = 0

    async def set(
        self, key: str, value: str, expires: KVTTL | int | None = None, not_exists: bool = False
    ) -> bool | None:
        if self.failures_before_success > 0:
            self.failures_before_success -= 1
            raise ConnectionError("cache unreachable")
        if self.fail_after_sets is not None and self.set_count >= self.fail_after_sets:
            raise ConnectionError("connection dropped")
        self.set_count += 1
        if key == ACTIVE_KEY:
            self.beat_times.append(time.monotonic())
        return await super().set(key=key, value=value, expires=expires, not_exists=not_exists)

    async def close_connection(self) -> None:
        self.closed = True


class SlowClosingCache(RecordingCache):
    """A cache whose close takes long enough for a short stop timeout to expire first."""

    def __init__(self, close_delay_seconds: float) -> None:
        super().__init__()
        self.close_delay_seconds = close_delay_seconds

    async def close_connection(self) -> None:
        await asyncio.sleep(self.close_delay_seconds)
        self.closed = True


async def wait_until(condition: Callable[[], bool], timeout_seconds: float = 2.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while not condition():
        if time.monotonic() > deadline:
            pytest.fail("condition not met before timeout")
        await asyncio.sleep(0.01)


def build_heartbeat(cache: RecordingCache, log: FakeLogger | None = None) -> WorkerHeartbeat:
    async def cache_factory() -> RecordingCache:
        return cache

    return WorkerHeartbeat(
        component_type=ComponentType.GIT_AGENT, cache_factory=cache_factory, interval_seconds=BEAT_INTERVAL, log=log
    )


@asynccontextmanager
async def running(heartbeat: WorkerHeartbeat) -> AsyncIterator[WorkerHeartbeat]:
    """Run the heartbeat for the duration of the block and stop it afterwards, whatever the block did."""
    heartbeat.start()
    try:
        yield heartbeat
    finally:
        await asyncio.to_thread(heartbeat.stop)


async def test_heartbeat_marks_worker_active_and_closes_cache_on_stop() -> None:
    cache = RecordingCache()
    heartbeat = build_heartbeat(cache=cache)

    async with running(heartbeat):
        await wait_until(lambda: ACTIVE_KEY in cache.storage and WORKER_KEY in cache.storage)
        assert heartbeat.running

    assert not heartbeat.running
    assert cache.closed


async def test_heartbeat_keeps_beating_while_the_main_loop_is_blocked() -> None:
    """The reason the heartbeat has its own thread: a stalled main loop must not stop it."""
    cache = RecordingCache()
    heartbeat = build_heartbeat(cache=cache)

    async with running(heartbeat):
        await wait_until(lambda: len(cache.beat_times) >= 1)
        beats_before = len(cache.beat_times)
        # Block this test's event loop the way a CPU-bound flow step blocks the worker's loop.
        time.sleep(BEAT_INTERVAL * 10)  # noqa: ASYNC251
        beats_during_block = len(cache.beat_times) - beats_before

    assert beats_during_block >= 3


async def test_heartbeat_logs_and_retries_a_failed_refresh() -> None:
    log = FakeLogger()
    cache = RecordingCache(failures_before_success=2)
    heartbeat = build_heartbeat(cache=cache, log=log)

    async with running(heartbeat):
        await wait_until(lambda: ACTIVE_KEY in cache.storage)

    assert log.exception_logs == ["Worker heartbeat refresh failed"] * 2


async def test_heartbeat_retries_opening_the_cache_connection() -> None:
    log = FakeLogger()
    cache = RecordingCache()
    attempts = 0

    async def flaky_cache_factory() -> RecordingCache:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ConnectionError("cache unreachable")
        return cache

    heartbeat = WorkerHeartbeat(
        component_type=ComponentType.GIT_AGENT,
        cache_factory=flaky_cache_factory,
        interval_seconds=BEAT_INTERVAL,
        log=log,
    )

    async with running(heartbeat):
        await wait_until(lambda: ACTIVE_KEY in cache.storage)

    assert attempts == 2
    assert log.exception_logs == ["Worker heartbeat refresh failed"]
    assert cache.closed


async def test_heartbeat_reconnects_after_a_failed_refresh() -> None:
    """A connection that breaks after it worked is closed and replaced, not retried forever."""
    log = FakeLogger()
    first_cache = RecordingCache(fail_after_sets=2)
    second_cache = RecordingCache()
    caches = iter([first_cache, second_cache])

    async def cache_factory() -> RecordingCache:
        return next(caches)

    heartbeat = WorkerHeartbeat(
        component_type=ComponentType.GIT_AGENT, cache_factory=cache_factory, interval_seconds=BEAT_INTERVAL, log=log
    )

    async with running(heartbeat):
        await wait_until(lambda: ACTIVE_KEY in second_cache.storage)

    assert first_cache.closed
    assert second_cache.closed
    assert log.exception_logs == ["Worker heartbeat refresh failed"]


async def test_stop_keeps_the_thread_while_it_is_still_finishing() -> None:
    """A stop whose wait times out must not let a later start spawn a second, unstoppable thread."""
    cache = SlowClosingCache(close_delay_seconds=0.5)
    heartbeat = build_heartbeat(cache=cache)
    heartbeat.start()
    await wait_until(lambda: ACTIVE_KEY in cache.storage)
    first_thread = heartbeat._thread

    await asyncio.to_thread(heartbeat.stop, timeout_seconds=0.05)

    assert heartbeat.running, "the thread is still closing its connection"
    heartbeat.start()
    assert heartbeat._thread is first_thread
    await wait_until(lambda: not heartbeat.running)
    assert cache.closed
    await asyncio.to_thread(heartbeat.stop)
    assert heartbeat._thread is None


async def test_heartbeat_start_is_idempotent_and_stop_without_start_is_safe() -> None:
    cache = RecordingCache()
    heartbeat = build_heartbeat(cache=cache)

    await asyncio.to_thread(heartbeat.stop)
    assert not heartbeat.running

    async with running(heartbeat):
        first_thread = heartbeat._thread
        heartbeat.start()
        assert heartbeat._thread is first_thread
