from __future__ import annotations

from infrahub.core.timestamp import Timestamp
from infrahub.lock import LOCK_PREFIX
from infrahub.locks.cleaner import StaleLockCleaner
from tests.adapters.cache import MemoryCache
from tests.adapters.worker_liveness import StaticWorkerLiveness

LIVE_WORKER = "live-worker"
DEAD_WORKER = "dead-worker"

GRAPH_LOCK_KEY = f"{LOCK_PREFIX}.global.graph"
SCHEMA_LOCK_KEY = f"{LOCK_PREFIX}.global.schema"
TOKENLESS_KEY = f"{LOCK_PREFIX}.diff-update.main__feature"
MISSING_KEY = f"{LOCK_PREFIX}.diff-update.main__feature__incremental"


def _lock_token(worker_id: str) -> str:
    return f"{Timestamp().to_string()}::{worker_id}"


def _build_cleaner(cache: MemoryCache) -> StaleLockCleaner:
    return StaleLockCleaner(cache=cache, worker_liveness=StaticWorkerLiveness(active_worker_ids={LIVE_WORKER}))


async def test_clears_only_locks_held_by_dead_workers() -> None:
    cache = MemoryCache()
    live_token = _lock_token(LIVE_WORKER)
    await cache.set(GRAPH_LOCK_KEY, _lock_token(DEAD_WORKER))
    await cache.set(SCHEMA_LOCK_KEY, live_token)
    await cache.set(TOKENLESS_KEY, "")
    # MISSING_KEY is intentionally never set.

    cleaner = _build_cleaner(cache)

    await cleaner.clear_if_holder_dead(keys=[GRAPH_LOCK_KEY, SCHEMA_LOCK_KEY, TOKENLESS_KEY, MISSING_KEY])

    # Only the dead-worker lock is dropped; the live-worker lock and the unparseable (empty-token) key stay.
    assert cache.storage == {SCHEMA_LOCK_KEY: live_token, TOKENLESS_KEY: ""}


async def test_no_keys_deleted_when_all_holders_live() -> None:
    cache = MemoryCache()
    graph_token = _lock_token(LIVE_WORKER)
    schema_token = _lock_token(LIVE_WORKER)
    await cache.set(GRAPH_LOCK_KEY, graph_token)
    await cache.set(SCHEMA_LOCK_KEY, schema_token)

    cleaner = _build_cleaner(cache)

    await cleaner.clear_if_holder_dead(keys=[GRAPH_LOCK_KEY, SCHEMA_LOCK_KEY])

    assert cache.storage == {GRAPH_LOCK_KEY: graph_token, SCHEMA_LOCK_KEY: schema_token}
