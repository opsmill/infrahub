from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub import lock
from infrahub.lock import LOCK_PREFIX, get_worker_id_from_lock_token

if TYPE_CHECKING:
    from infrahub.services.adapters.cache import InfrahubCache

# The distributed lock value lives in the cache backend under this key.
MERGE_LOCK_KEY = f"{LOCK_PREFIX}.merge.all_branches"


class MergeLocker:
    lock_namespace = "merge"

    def __init__(self) -> None:
        self.lock_registry = lock.registry

    def acquire_global_lock(self) -> lock.InfrahubLock:
        return self.lock_registry.get(name="all_branches", namespace=self.lock_namespace)


async def get_merge_lock_holder_worker_id(cache: InfrahubCache) -> str | None:
    """Return the worker id holding the global merge lock, without acquiring it.

    ``None`` when the lock is not held (no merge in progress) or its token is unreadable, so the
    failure check never treats a dropped lock as one held by a live worker.
    """
    return get_worker_id_from_lock_token(await cache.get(key=MERGE_LOCK_KEY))
