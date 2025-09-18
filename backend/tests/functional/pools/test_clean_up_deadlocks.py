from unittest.mock import AsyncMock, patch

from infrahub.lock import InfrahubLock
from infrahub.pools.tasks import clean_up_deadlocks
from infrahub.services import InfrahubServices
from infrahub.services.adapters.cache.redis import RedisCache


async def test_clean_up_deadlocks():
    redis_cache = AsyncMock(RedisCache)
    redis_cache.list_keys.return_value = ["lock.repository.sample-infrahub"]
    redis_cache.get_values.return_value = ["2025-09-18T12:07:24.654862Z::800b4a90-87cd-458f-8c68-b0b5ebb81046"]
    service = await InfrahubServices.new(cache=redis_cache)

    with patch("infrahub.pools.tasks.lock") as lock:
        infrahub_lock = AsyncMock(InfrahubLock)
        lock.registry.get_existing.return_value = infrahub_lock

        await clean_up_deadlocks(service=service)

        assert infrahub_lock.release.assert_awaited_once()
