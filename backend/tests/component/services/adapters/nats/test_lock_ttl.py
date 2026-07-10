import asyncio

import pytest

from infrahub import config
from infrahub.lock import LOCK_PREFIX, InfrahubLockRegistry
from infrahub.services import InfrahubServices
from infrahub.services.adapters.cache.nats import NATSCache


async def _registry() -> tuple[InfrahubLockRegistry, InfrahubServices]:
    cache = await NATSCache.new()
    service = await InfrahubServices.new(cache=cache)
    return InfrahubLockRegistry(local_only=False, service=service), service


async def test_init_lock_auto_expires(nats: dict[int, int] | None) -> None:
    """A global init lock with a TTL is dropped by NATS on its own, even if it is never released."""
    if config.SETTINGS.cache.driver != config.CacheDriver.NATS:
        pytest.skip("Must use NATS to run this test")

    registry, service = await _registry()
    lock_obj = registry.get(name="global.init.test", ttl=2)
    key = f"{LOCK_PREFIX}.global.init.test"

    await lock_obj.acquire()
    assert await service.cache.get(key) is not None

    await asyncio.sleep(3)
    # NATS expired the key without anyone releasing the lock, so a crashed holder cannot deadlock startup.
    assert await service.cache.get(key) is None

    # Releasing a lock that already expired must not raise back to the caller.
    await lock_obj.release()
    await service.cache.close_connection()


async def test_lock_acquire_release_cycle(nats: dict[int, int] | None) -> None:
    """A lock with no TTL is held until released and then frees the key."""
    if config.SETTINGS.cache.driver != config.CacheDriver.NATS:
        pytest.skip("Must use NATS to run this test")

    registry, service = await _registry()
    lock_obj = registry.get(name="repository.repo-cycle")
    key = f"{LOCK_PREFIX}.repository.repo-cycle"

    await lock_obj.acquire()
    assert await service.cache.get(key) is not None
    await lock_obj.release()
    assert await service.cache.get(key) is None

    await service.cache.close_connection()
