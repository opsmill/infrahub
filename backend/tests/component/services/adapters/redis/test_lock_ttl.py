import asyncio

import pytest
from redis.exceptions import LockNotOwnedError

from infrahub import config
from infrahub.lock import LOCK_PREFIX, InfrahubLockRegistry


async def test_init_lock_auto_expires(redis: dict[int, int] | None) -> None:
    """A global init lock with a TTL is dropped by Redis on its own, even if it is never released."""
    if config.SETTINGS.cache.driver != config.CacheDriver.Redis:
        pytest.skip("Must use Redis to run this test")

    registry = InfrahubLockRegistry(local_only=False)
    lock_obj = registry.get(name="global.init.test", ttl=1)
    redis_key = f"{LOCK_PREFIX}.global.init.test"

    await lock_obj.acquire()
    assert await registry.connection.get(redis_key) is not None

    await asyncio.sleep(1.2)
    # Redis expired the key without anyone releasing the lock, so a crashed holder cannot deadlock startup.
    assert await registry.connection.get(redis_key) is None

    # Releasing a lock that already expired must not raise back to the caller.
    await lock_obj.release()


async def test_lock_without_ttl_persists(redis: dict[int, int] | None) -> None:
    if config.SETTINGS.cache.driver != config.CacheDriver.Redis:
        pytest.skip("Must use Redis to run this test")

    registry = InfrahubLockRegistry(local_only=False)
    lock_obj = registry.get(name="global.persistent.test")
    redis_key = f"{LOCK_PREFIX}.global.persistent.test"

    await lock_obj.acquire()
    try:
        assert await registry.connection.ttl(redis_key) == -1  # -1 means the key has no expiry
    finally:
        await lock_obj.release()
    assert await registry.connection.get(redis_key) is None


async def test_release_reraises_when_lock_lost_without_ttl(redis: dict[int, int] | None) -> None:
    """Without a TTL, losing the lock before release is unexpected and must surface to the caller."""
    if config.SETTINGS.cache.driver != config.CacheDriver.Redis:
        pytest.skip("Must use Redis to run this test")

    registry = InfrahubLockRegistry(local_only=False)
    lock_obj = registry.get(name="global.lost.test")
    redis_key = f"{LOCK_PREFIX}.global.lost.test"

    await lock_obj.acquire()
    # Simulate the key disappearing from Redis under us; with no TTL this is not an expected state.
    await registry.connection.delete(redis_key)

    with pytest.raises(LockNotOwnedError):
        await lock_obj.release()
