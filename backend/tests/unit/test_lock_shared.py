from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from infrahub.exceptions import LockError, LockWaitTimeoutError
from infrahub.lock import LOCK_PREFIX, InfrahubLock, InfrahubSharedLock
from infrahub.locks.shared_holders.local import LocalSharedHolderStore

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

LOCK_NAME = "resource_pool.pool-1"
TTL_SECONDS = 1
WAIT_SECONDS = 30


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class RecordingSharedHolderStore(LocalSharedHolderStore):
    """Keeps the holders in this process and records every key written, renewals included."""

    def __init__(self, clock: FakeClock) -> None:
        super().__init__(clock=clock)
        self.added: list[str] = []

    async def add(self, key: str, token: str, ttl_seconds: int) -> None:
        self.added.append(key)
        await super().add(key=key, token=token, ttl_seconds=ttl_seconds)


async def _wait_until(condition: Callable[[], Awaitable[bool]]) -> None:
    async def _poll() -> None:
        while not await condition():  # noqa: ASYNC110
            await asyncio.sleep(0.01)

    await asyncio.wait_for(_poll(), timeout=5)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def store(clock: FakeClock) -> RecordingSharedHolderStore:
    return RecordingSharedHolderStore(clock=clock)


@pytest.fixture
def mutex() -> InfrahubLock:
    return InfrahubLock(name=LOCK_NAME)


@pytest.fixture
def shared_lock(mutex: InfrahubLock, store: RecordingSharedHolderStore, clock: FakeClock) -> InfrahubSharedLock:
    return InfrahubSharedLock(
        name=LOCK_NAME,
        mutex=mutex,
        store=store,
        ttl_seconds=TTL_SECONDS,
        wait_seconds=WAIT_SECONDS,
        poll_seconds=0.01,
        clock=clock,
    )


async def _has_holders(store: RecordingSharedHolderStore) -> bool:
    return await store.has_holders(pattern=f"{LOCK_PREFIX}.shared.{LOCK_NAME}.*")


async def test_two_shared_holders_hold_the_lock_at_the_same_time(shared_lock: InfrahubSharedLock) -> None:
    both_inside = asyncio.Barrier(2)

    async def hold() -> None:
        async with shared_lock.shared():
            await asyncio.wait_for(both_inside.wait(), timeout=5)

    await asyncio.gather(hold(), hold())


async def _let_other_tasks_run() -> None:
    for _ in range(10):
        await asyncio.sleep(0)


async def _hold_exclusively(shared_lock: InfrahubSharedLock, inside: asyncio.Event, release: asyncio.Event) -> None:
    async with shared_lock.exclusive():
        inside.set()
        await asyncio.wait_for(release.wait(), timeout=5)


async def test_an_exclusive_request_waits_until_every_shared_holder_releases(
    shared_lock: InfrahubSharedLock, mutex: InfrahubLock
) -> None:
    holder_inside = asyncio.Event()
    holder_release = asyncio.Event()
    exclusive_inside = asyncio.Event()

    async def hold() -> None:
        async with shared_lock.shared():
            holder_inside.set()
            await asyncio.wait_for(holder_release.wait(), timeout=5)

    holder = asyncio.create_task(hold())
    await asyncio.wait_for(holder_inside.wait(), timeout=5)
    exclusive = asyncio.create_task(
        _hold_exclusively(shared_lock=shared_lock, inside=exclusive_inside, release=asyncio.Event())
    )
    await _wait_until(mutex.locked)
    await _let_other_tasks_run()

    assert not exclusive_inside.is_set()

    holder_release.set()
    await asyncio.wait_for(exclusive_inside.wait(), timeout=5)
    await holder
    exclusive.cancel()
    await asyncio.gather(exclusive, return_exceptions=True)
    assert not await mutex.locked()


async def test_a_shared_request_waits_while_the_lock_is_held_exclusively(
    shared_lock: InfrahubSharedLock, store: RecordingSharedHolderStore
) -> None:
    exclusive_inside = asyncio.Event()
    exclusive_release = asyncio.Event()
    shared_inside = asyncio.Event()

    async def hold_shared() -> None:
        async with shared_lock.shared():
            shared_inside.set()

    exclusive = asyncio.create_task(
        _hold_exclusively(shared_lock=shared_lock, inside=exclusive_inside, release=exclusive_release)
    )
    await asyncio.wait_for(exclusive_inside.wait(), timeout=5)
    shared = asyncio.create_task(hold_shared())
    await _let_other_tasks_run()

    assert not shared_inside.is_set()
    assert store.added == []

    exclusive_release.set()
    await asyncio.wait_for(asyncio.gather(exclusive, shared), timeout=5)

    assert shared_inside.is_set()
    assert len(store.added) == 1


async def test_an_exclusive_request_still_shared_at_the_wait_limit_fails_and_leaves_the_lock_free(
    shared_lock: InfrahubSharedLock, mutex: InfrahubLock, store: RecordingSharedHolderStore, clock: FakeClock
) -> None:
    await store.add(key=f"{LOCK_PREFIX}.shared.{LOCK_NAME}.holder", token="token", ttl_seconds=3600)
    exclusive = asyncio.create_task(shared_lock.acquire_exclusive())
    await _wait_until(mutex.locked)

    clock.advance(WAIT_SECONDS)

    with pytest.raises(
        LockWaitTimeoutError,
        match=rf"^The lock {LOCK_NAME} was still held in shared mode after {WAIT_SECONDS} seconds$",
    ):
        await asyncio.wait_for(exclusive, timeout=5)
    assert not await mutex.locked()


async def test_the_record_of_a_holder_that_stopped_renewing_it_expires(
    shared_lock: InfrahubSharedLock, mutex: InfrahubLock, store: RecordingSharedHolderStore, clock: FakeClock
) -> None:
    await store.add(key=f"{LOCK_PREFIX}.shared.{LOCK_NAME}.dead-holder", token="token", ttl_seconds=TTL_SECONDS)
    exclusive_inside = asyncio.Event()
    exclusive = asyncio.create_task(
        _hold_exclusively(shared_lock=shared_lock, inside=exclusive_inside, release=asyncio.Event())
    )
    await _wait_until(mutex.locked)
    await _let_other_tasks_run()

    assert not exclusive_inside.is_set()

    clock.advance(TTL_SECONDS)

    await asyncio.wait_for(exclusive_inside.wait(), timeout=5)
    exclusive.cancel()
    await asyncio.gather(exclusive, return_exceptions=True)
    assert not await mutex.locked()


async def test_a_shared_holder_renews_its_record_while_it_holds_the_lock(
    shared_lock: InfrahubSharedLock, store: RecordingSharedHolderStore, clock: FakeClock
) -> None:
    async with shared_lock.shared():
        clock.advance(TTL_SECONDS * 0.9)

        async def renewed() -> bool:
            return len(store.added) == 2

        await _wait_until(renewed)
        clock.advance(TTL_SECONDS * 0.5)

        assert store.added[0] == store.added[1]

        assert await _has_holders(store)

    assert not await _has_holders(store)


class FailingOnceSharedHolderStore(RecordingSharedHolderStore):
    """Fails the first renewal of a record, as an unreachable cache would."""

    async def add(self, key: str, token: str, ttl_seconds: int) -> None:
        await super().add(key=key, token=token, ttl_seconds=ttl_seconds)
        if len(self.added) == 2:
            raise ConnectionError("cache unreachable")


async def test_a_shared_holder_keeps_renewing_its_record_after_a_failed_renewal(
    mutex: InfrahubLock, clock: FakeClock
) -> None:
    store = FailingOnceSharedHolderStore(clock=clock)
    shared_lock = InfrahubSharedLock(
        name=LOCK_NAME, mutex=mutex, store=store, ttl_seconds=TTL_SECONDS, wait_seconds=WAIT_SECONDS, clock=clock
    )

    async def renewed_after_the_failure() -> bool:
        return len(store.added) == 3

    async with shared_lock.shared():
        await _wait_until(renewed_after_the_failure)

        assert store.added[0] == store.added[1] == store.added[2]

    assert not await _has_holders(store)


async def test_a_shared_request_from_a_task_already_holding_it_returns_at_once(
    shared_lock: InfrahubSharedLock, store: RecordingSharedHolderStore
) -> None:
    async with shared_lock.shared():
        async with shared_lock.shared():
            assert await _has_holders(store)
        assert await _has_holders(store)

    assert not await _has_holders(store)


async def test_a_shared_request_from_a_task_holding_it_exclusively_returns_at_once(
    shared_lock: InfrahubSharedLock, mutex: InfrahubLock, store: RecordingSharedHolderStore
) -> None:
    async with shared_lock.exclusive():
        async with shared_lock.shared():
            assert not await _has_holders(store)
        assert await mutex.locked()

    assert not await mutex.locked()


async def test_an_exclusive_request_from_a_task_holding_it_shared_is_refused(
    shared_lock: InfrahubSharedLock, mutex: InfrahubLock
) -> None:
    async with shared_lock.shared():
        with pytest.raises(
            LockError, match=rf"^The lock {LOCK_NAME} is held in shared mode by this task and cannot be made exclusive$"
        ):
            await shared_lock.acquire_exclusive()

    assert not await mutex.locked()
