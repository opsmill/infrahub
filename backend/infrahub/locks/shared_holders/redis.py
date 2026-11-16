from __future__ import annotations

from typing import TYPE_CHECKING

from .interface import SharedHolderStore

if TYPE_CHECKING:
    import redis.asyncio as redis


def _holder_key(key: str, holder: str) -> str:
    return f"{key}.{holder}"


class RedisSharedHolderStore(SharedHolderStore):
    """Keeps each holder as a key that expires on its own unless renewed, and the ids of a lock's holders in a set.

    The set lets a lock find its holders without scanning the keys; an id whose key has expired is dropped
    from it when the lock is checked, and Redis deletes the set once it is empty.
    """

    def __init__(self, connection: redis.Redis) -> None:
        self._connection = connection

    async def add(self, key: str, holder: str, token: str, ttl_seconds: int) -> None:
        # The key is written before the id, so a lock that finds the id also finds the key unless it expired.
        async with self._connection.pipeline(transaction=False) as pipe:
            pipe.set(name=_holder_key(key=key, holder=holder), value=token, ex=ttl_seconds)
            pipe.sadd(key, holder)
            await pipe.execute()

    async def remove(self, key: str, holder: str) -> None:
        async with self._connection.pipeline(transaction=False) as pipe:
            pipe.delete(_holder_key(key=key, holder=holder))
            pipe.srem(key, holder)
            await pipe.execute()

    async def has_holders(self, key: str) -> bool:
        holders = [
            member.decode() if isinstance(member, bytes) else member for member in await self._connection.smembers(key)
        ]
        if not holders:
            return False
        async with self._connection.pipeline(transaction=False) as pipe:
            for holder in holders:
                pipe.exists(_holder_key(key=key, holder=holder))
            alive = await pipe.execute()
        expired = [holder for holder, exists in zip(holders, alive, strict=True) if not exists]
        if expired:
            await self._connection.srem(key, *expired)
        return len(expired) < len(holders)
