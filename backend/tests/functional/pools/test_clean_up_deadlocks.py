from unittest.mock import AsyncMock

from infrahub.pools.tasks import clean_up_deadlocks
from infrahub.services import InfrahubServices
from infrahub.services.adapters.cache.redis import RedisCache
from infrahub.services.component import InfrahubComponent, WorkerInfo


async def test_clean_up_deadlocks(default_branch):
    redis_cache = AsyncMock(RedisCache)
    redis_cache.list_keys.return_value = ["lock.repository.sample-infrahub"]
    redis_cache.get_values.return_value = ["2025-09-18T12:07:24.654862Z::800b4a90-87cd-458f-8c68-b0b5ebb81046"]
    redis_cache.delete.return_value = True

    component = AsyncMock(InfrahubComponent)
    component.list_workers.return_value = [WorkerInfo(identity="800b4a90-87cd-458f-8c68-b0b5ebb81046")]

    service = await InfrahubServices.new(cache=redis_cache, component=component)

    await clean_up_deadlocks(service=service)

    redis_cache.list_keys.assert_awaited_once()
    redis_cache.get_values.assert_awaited_once()
    component.list_workers.assert_awaited_once()
    redis_cache.delete.assert_awaited_once()
