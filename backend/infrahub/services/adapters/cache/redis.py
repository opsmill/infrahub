from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub import config
from infrahub.services.adapters.cache import InfrahubCache
from infrahub.services.adapters.cache.connection import build_redis_connection

if TYPE_CHECKING:
    from infrahub.message_bus.types import KVTTL


class RedisCache(InfrahubCache):
    def __init__(self) -> None:
        self.connection = build_redis_connection(config.SETTINGS.cache)

    async def delete(self, key: str) -> None:
        await self.connection.delete(key)

    async def get(self, key: str) -> str | None:
        value = await self.connection.get(name=key)
        if value is not None:
            return value.decode()
        return None

    async def get_values(self, keys: list[str]) -> list[str | None]:
        values = await self.connection.mget(keys=keys)
        return [value.decode() if value is not None else value for value in values]

    async def list_keys(self, filter_pattern: str) -> list[str]:
        cursor = 0
        has_remaining_keys = True
        keys = []
        while has_remaining_keys:
            cursor, scanned_keys = await self.connection.scan(cursor=cursor, match=filter_pattern, count=100)
            keys.extend(scanned_keys)
            if cursor == 0:
                has_remaining_keys = False

        return [key.decode() for key in keys]

    async def set(
        self, key: str, value: str, expires: KVTTL | int | None = None, not_exists: bool = False
    ) -> bool | None:
        # redis-py cannot encode an IntEnum (e.g. KVTTL) directly, so coerce the TTL to a plain int.
        ex = int(expires) if expires else None
        return await self.connection.set(name=key, value=value, ex=ex, nx=not_exists)

    @classmethod
    async def new(cls) -> RedisCache:
        return cls()

    async def close_connection(self) -> None:
        await self.connection.aclose()
