from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.components import ComponentType
from infrahub.lock import LOCK_PREFIX
from infrahub.locks.tasks import clean_up_deadlocks
from infrahub.services import InfrahubServices
from infrahub.services.component import InfrahubComponent
from tests.adapters.cache import MemoryCache
from tests.adapters.message_bus import BusRecorder

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

DEAD_WORKER = "800b4a90-87cd-458f-8c68-b0b5ebb81046"


async def test_clean_up_deadlocks(db: InfrahubDatabase, default_branch: Branch) -> None:
    cache = MemoryCache()
    stale_key = f"{LOCK_PREFIX}.repository.sample-infrahub"
    # A lock held by a worker that is no longer active, acquired long enough ago to pass the age gate.
    await cache.set(key=stale_key, value=f"2025-09-18T12:07:24.654862Z::{DEAD_WORKER}")

    component = InfrahubComponent(
        cache=cache, db=db, message_bus=BusRecorder(), component_type=ComponentType.API_SERVER
    )
    # refresh_heartbeat marks THIS worker active; DEAD_WORKER, which holds the stale lock, is not.
    await component.refresh_heartbeat()
    service = await InfrahubServices.new(cache=cache, component=component)

    await clean_up_deadlocks(service=service)

    assert await cache.list_keys(filter_pattern=f"{LOCK_PREFIX}*") == []
