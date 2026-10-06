from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

    from infrahub.services.adapters.cache import InfrahubCache


class CacheFlowRunReservations:
    """Reserve a scheduled flow run for one worker so that concurrent workers do not both claim it."""

    def __init__(self, cache: InfrahubCache, owner: str, ttl: int) -> None:
        self._cache = cache
        self._owner = owner
        self._ttl = ttl

    async def reserve(self, flow_run_id: UUID) -> bool:
        """Reserve the run for the next `ttl` seconds, succeeding when it is free or already reserved by this owner."""
        key = self._key(flow_run_id=flow_run_id)
        if await self._cache.set(key=key, value=self._owner, expires=self._ttl, not_exists=True):
            return True
        if await self._cache.get(key=key) != self._owner:
            return False
        # A run held since an earlier poll may be about to expire, and the claim that follows must not outlive it.
        await self._cache.set(key=key, value=self._owner, expires=self._ttl)
        return True

    async def release(self, flow_run_id: UUID) -> None:
        """Release the run, leaving a reservation held by another owner in place."""
        key = self._key(flow_run_id=flow_run_id)
        if await self._cache.get(key=key) == self._owner:
            await self._cache.delete(key=key)

    def _key(self, flow_run_id: UUID) -> str:
        return f"flow-run-pending-{flow_run_id}"
