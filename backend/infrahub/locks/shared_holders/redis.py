from __future__ import annotations

from typing import TYPE_CHECKING

from . import SharedHolderStore

if TYPE_CHECKING:
    import redis.asyncio as redis


class RedisSharedHolderStore(SharedHolderStore):
    """Keeps each holder as a Redis key that expires on its own when a dead worker stops renewing it."""

    def __init__(self, connection: redis.Redis) -> None:
        self._connection = connection

    async def add(self, key: str, token: str, ttl_seconds: int) -> None:
        await self._connection.set(name=key, value=token, ex=ttl_seconds)

    async def remove(self, key: str) -> None:
        await self._connection.delete(key)

    async def has_holders(self, pattern: str) -> bool:
        async for _ in self._connection.scan_iter(match=pattern, count=100):
            return True
        return False
