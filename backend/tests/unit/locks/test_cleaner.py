from __future__ import annotations

from typing import TYPE_CHECKING, cast

from infrahub.components import ComponentType
from infrahub.core.timestamp import Timestamp
from infrahub.lock import LOCK_PREFIX
from infrahub.locks.cleaner import StaleLockCleaner
from infrahub.services.component import InfrahubComponent
from infrahub.worker import WORKER_IDENTITY
from tests.adapters.cache import MemoryCache
from tests.adapters.message_bus import BusRecorder

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

DEAD_WORKER = "dead-worker"

DEAD_KEY = f"{LOCK_PREFIX}.global.graph"
LIVE_KEY = f"{LOCK_PREFIX}.global.schema"
TOKENLESS_KEY = f"{LOCK_PREFIX}.diff-update.main__feature"
MISSING_KEY = f"{LOCK_PREFIX}.diff-update.main__feature__incremental"


def _lock_token(worker_id: str) -> str:
    return f"{Timestamp().to_string()}::{worker_id}"


async def _build_cleaner(cache: MemoryCache) -> StaleLockCleaner:
    # list_active_worker_ids reads only the cache heartbeats, so a cache-backed component needs no database.
    db = cast("InfrahubDatabase", None)
    component = InfrahubComponent(
        cache=cache, db=db, message_bus=BusRecorder(), component_type=ComponentType.API_SERVER
    )
    await component.refresh_heartbeat()  # marks WORKER_IDENTITY active in the cache
    return StaleLockCleaner(cache=cache, component=component, default_branch_name="main")


async def test_clears_only_locks_held_by_dead_workers() -> None:
    cache = MemoryCache()
    live_token = _lock_token(WORKER_IDENTITY)
    await cache.set(DEAD_KEY, _lock_token(DEAD_WORKER))
    await cache.set(LIVE_KEY, live_token)
    await cache.set(TOKENLESS_KEY, "")
    # MISSING_KEY is intentionally never set.

    cleaner = await _build_cleaner(cache)

    deleted = await cleaner.clear_if_holder_dead(keys=[DEAD_KEY, LIVE_KEY, TOKENLESS_KEY, MISSING_KEY])

    # Only the dead-worker lock is dropped; the live-worker lock and the unparseable/missing keys stay.
    assert deleted == [DEAD_KEY]
    assert await cache.get(DEAD_KEY) is None
    assert await cache.get(LIVE_KEY) == live_token
    # The unparseable (empty-token) key is left in place, not deleted.
    assert TOKENLESS_KEY in cache.storage
    assert await cache.get(MISSING_KEY) is None


async def test_no_keys_deleted_when_all_holders_live() -> None:
    cache = MemoryCache()
    dead_key_token = _lock_token(WORKER_IDENTITY)
    live_key_token = _lock_token(WORKER_IDENTITY)
    await cache.set(DEAD_KEY, dead_key_token)
    await cache.set(LIVE_KEY, live_key_token)

    cleaner = await _build_cleaner(cache)

    deleted = await cleaner.clear_if_holder_dead(keys=[DEAD_KEY, LIVE_KEY])

    assert deleted == []
    assert await cache.get(DEAD_KEY) == dead_key_token
    assert await cache.get(LIVE_KEY) == live_key_token
