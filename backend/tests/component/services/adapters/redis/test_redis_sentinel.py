from uuid import uuid4

import pytest

from infrahub import config
from infrahub.lock import InfrahubLockRegistry
from infrahub.message_bus.types import KVTTL
from infrahub.services.adapters.cache.redis import RedisCache


async def test_sentinel_cache_set_get(redis_sentinel: dict[int, int] | None) -> None:
    if config.SETTINGS.cache.driver != config.CacheDriver.Redis or not redis_sentinel:
        pytest.skip("Must use Redis with a Sentinel topology to run this test")

    cache = RedisCache()
    key = f"ci_testing:{uuid4()}"
    value = "set via sentinel"

    assert await cache.get(key=key) is None
    await cache.set(key=key, value=value, expires=KVTTL.ONE)
    assert await cache.get(key=key) == value

    await cache.close_connection()


async def test_sentinel_lock_acquire_release(redis_sentinel: dict[int, int] | None) -> None:
    if config.SETTINGS.cache.driver != config.CacheDriver.Redis or not redis_sentinel:
        pytest.skip("Must use Redis with a Sentinel topology to run this test")

    registry = InfrahubLockRegistry(local_only=False)
    lock = registry.get(name=f"ci_testing.{uuid4()}")

    await lock.acquire()
    assert await lock.locked() is True
    await lock.release()
    assert await lock.locked() is False
