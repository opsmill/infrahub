from __future__ import annotations

from typing import TYPE_CHECKING

from . import SharedHolderStore

if TYPE_CHECKING:
    from infrahub.services.adapters.cache import InfrahubCache


class CacheSharedHolderStore(SharedHolderStore):
    """Keeps each holder as a cache key that expires on its own when a dead worker stops renewing it."""

    def __init__(self, cache: InfrahubCache) -> None:
        self._cache = cache

    async def add(self, key: str, token: str, ttl_seconds: int) -> None:
        await self._cache.set(key=key, value=token, expires=ttl_seconds)

    async def remove(self, key: str) -> None:
        await self._cache.delete(key=key)

    async def has_holders(self, pattern: str) -> bool:
        return bool(await self._cache.list_keys(filter_pattern=pattern))
