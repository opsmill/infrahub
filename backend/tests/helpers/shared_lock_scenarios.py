"""Scenarios a shared lock must pass on every distributed backend, each run between two registries as two workers."""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

from infrahub.lock import LOCK_PREFIX

if TYPE_CHECKING:
    from infrahub.lock import InfrahubLockRegistry, InfrahubSharedLock

TIMEOUT_SECONDS = 10


def unique_lock_name() -> str:
    return f"resource_pool.{uuid.uuid4()}"


async def _wait_until_locked(registry: InfrahubLockRegistry, name: str) -> None:
    async def _poll() -> None:
        while not await registry.get(name=name).locked():  # noqa: ASYNC110
            await asyncio.sleep(0.05)

    await asyncio.wait_for(_poll(), timeout=TIMEOUT_SECONDS)


async def _hold(lock: InfrahubSharedLock, exclusive: bool, inside: asyncio.Event, release: asyncio.Event) -> None:
    async with lock.exclusive() if exclusive else lock.shared():
        inside.set()
        await asyncio.wait_for(release.wait(), timeout=TIMEOUT_SECONDS)


async def exclusive_waits_for_the_shared_holder_of_another_worker(
    worker_a: InfrahubLockRegistry, worker_b: InfrahubLockRegistry
) -> None:
    name = unique_lock_name()
    shared_inside, shared_release = asyncio.Event(), asyncio.Event()
    exclusive_inside, exclusive_release = asyncio.Event(), asyncio.Event()
    holder = asyncio.create_task(
        _hold(lock=worker_a.get_shared(name=name), exclusive=False, inside=shared_inside, release=shared_release)
    )
    await asyncio.wait_for(shared_inside.wait(), timeout=TIMEOUT_SECONDS)
    exclusive = asyncio.create_task(
        _hold(lock=worker_b.get_shared(name=name), exclusive=True, inside=exclusive_inside, release=exclusive_release)
    )
    await _wait_until_locked(registry=worker_b, name=name)

    assert not exclusive_inside.is_set()

    shared_release.set()
    await asyncio.wait_for(exclusive_inside.wait(), timeout=TIMEOUT_SECONDS)
    exclusive_release.set()
    await asyncio.wait_for(asyncio.gather(holder, exclusive), timeout=TIMEOUT_SECONDS)

    assert not await worker_b.get(name=name).locked()
    assert not await worker_b.shared_holder_store.has_holders(pattern=f"{LOCK_PREFIX}.shared.{name}.*")


async def shared_waits_while_another_worker_holds_it_exclusively(
    worker_a: InfrahubLockRegistry, worker_b: InfrahubLockRegistry
) -> None:
    name = unique_lock_name()
    exclusive_inside, exclusive_release = asyncio.Event(), asyncio.Event()
    shared_inside, shared_release = asyncio.Event(), asyncio.Event()
    exclusive = asyncio.create_task(
        _hold(lock=worker_a.get_shared(name=name), exclusive=True, inside=exclusive_inside, release=exclusive_release)
    )
    await asyncio.wait_for(exclusive_inside.wait(), timeout=TIMEOUT_SECONDS)
    holder = asyncio.create_task(
        _hold(lock=worker_b.get_shared(name=name), exclusive=False, inside=shared_inside, release=shared_release)
    )
    for _ in range(10):
        await asyncio.sleep(0)

    assert not shared_inside.is_set()
    assert not await worker_b.shared_holder_store.has_holders(pattern=f"{LOCK_PREFIX}.shared.{name}.*")

    exclusive_release.set()
    await asyncio.wait_for(shared_inside.wait(), timeout=TIMEOUT_SECONDS)

    assert await worker_a.shared_holder_store.has_holders(pattern=f"{LOCK_PREFIX}.shared.{name}.*")

    shared_release.set()
    await asyncio.wait_for(asyncio.gather(exclusive, holder), timeout=TIMEOUT_SECONDS)


async def the_record_of_a_holder_that_stopped_renewing_it_expires(worker: InfrahubLockRegistry) -> None:
    name = unique_lock_name()
    pattern = f"{LOCK_PREFIX}.shared.{name}.*"
    await worker.shared_holder_store.add(key=f"{LOCK_PREFIX}.shared.{name}.dead-holder", token="token", ttl_seconds=2)

    assert await worker.shared_holder_store.has_holders(pattern=pattern)

    lock = worker.get_shared(name=name)
    await asyncio.wait_for(lock.acquire_exclusive(), timeout=TIMEOUT_SECONDS)
    await lock.release_exclusive()

    assert not await worker.shared_holder_store.has_holders(pattern=pattern)
