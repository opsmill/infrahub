from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.lock import get_worker_id_from_lock_token
from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub.services.adapters.cache import InfrahubCache
    from infrahub.services.component import InfrahubComponent

log = get_logger()


class StaleLockCleaner:
    """Drop distributed locks a dead flow left held, sparing those a live worker still holds.

    A hard-killed merge leaks no-TTL distributed locks (diff-update, global graph, global schema)
    that silently block the next merge until the deadlock reaper eventually clears them. Unlike the
    reaper this applies no age threshold: recovery already proves the merge dead. The per-key
    liveness check is what protects a lock legitimately held by a live flow — a running branch-diff
    computation or a schema load on another branch — so those are left untouched.
    """

    def __init__(self, cache: InfrahubCache, component: InfrahubComponent) -> None:
        self.cache = cache
        self.component = component

    async def clear_if_holder_dead(self, keys: list[str]) -> None:
        """Delete each lock key whose holder is not an active worker.

        A key with no token, an unparseable token, or a token naming a live worker is left in place.
        """
        active_worker_ids = await self._active_worker_ids()
        for key in keys:
            token = await self.cache.get(key=key)
            worker_id = get_worker_id_from_lock_token(token)
            if worker_id is None or worker_id in active_worker_ids:
                continue
            await self.cache.delete(key=key)
            log.warning("lock.stale.cleared", key=key, worker_id=worker_id)

    async def _active_worker_ids(self) -> set[str]:
        return await self.component.list_active_worker_ids()
