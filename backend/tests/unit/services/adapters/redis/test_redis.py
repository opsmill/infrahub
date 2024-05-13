import asyncio
from uuid import uuid4

import pytest

from infrahub import config
from infrahub.message_bus.types import KVTTL
from infrahub.services.adapters.cache.redis import RedisCache


async def test_get():
    if config.SETTINGS.cache.driver != config.CacheDriver.Redis:
        pytest.skip("Must use Redis to run this test")

    redis = RedisCache()
    key = f"ci_testing:{uuid4()}"
    value = "I exist"
    initial = await redis.get(key=key)
    await redis.set(key=key, value=value, expires=KVTTL.ONE)
    after_set = await redis.get(key=key)
    await asyncio.sleep(1.1)
    after_expiry = await redis.get(key=key)

    assert initial is None
    assert after_set == value
    assert after_expiry is None


async def test_list_keys():
    if config.SETTINGS.cache.driver != config.CacheDriver.Redis:
        pytest.skip("Must use Redis to run this test")

    redis = RedisCache()
    base_key = f"ci_testing:{uuid4()}"
    iterations = 1005
    for i in range(iterations):
        await redis.set(key=f"{base_key}:{i + 1}", value="Value set", expires=KVTTL.TEN)

    keys = await redis.list_keys(filter_pattern=f"{base_key}:*")

    assert len(keys) == iterations
    assert f"{base_key}:1" in keys
    assert f"{base_key}:1005" in keys
