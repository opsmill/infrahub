from unittest.mock import AsyncMock

from infrahub.core.branch import Branch
from infrahub.lock import LOCK_PREFIX
from infrahub.locks.tasks import clean_up_deadlocks
from infrahub.services import InfrahubServices
from infrahub.services.component import InfrahubComponent, WorkerInfo
from tests.adapters.cache import MemoryCache


async def test_clean_up_deadlocks(default_branch: Branch) -> None:
    cache = MemoryCache()
    await cache.set(
        key="lock.repository.sample-infrahub", value="2025-09-18T12:07:24.654862Z::800b4a90-87cd-458f-8c68-b0b5ebb81046"
    )

    component = AsyncMock(InfrahubComponent)
    component.list_workers.return_value = [WorkerInfo(identity="800b4a90-87cd-458f-8c68-b0b5ebb81046")]

    service = await InfrahubServices.new(cache=cache, component=component)

    await clean_up_deadlocks(service=service)

    component.list_workers.assert_awaited_once()
    assert not (await cache.list_keys(filter_pattern=f"{LOCK_PREFIX}*"))
