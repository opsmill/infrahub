from __future__ import annotations

from typing import TYPE_CHECKING

import redis.asyncio as redis

from infrahub import config
from infrahub.services.adapters.cache import InfrahubCache

if TYPE_CHECKING:
    from infrahub.message_bus.types import KVTTL


class RedisCache(InfrahubCache):
    def __init__(self) -> None:
        self.connection = redis.Redis(
            host=config.SETTINGS.cache.address,
            port=config.SETTINGS.cache.service_port,
            db=config.SETTINGS.cache.database,
            ssl=config.SETTINGS.cache.tls_enabled,
            ssl_cert_reqs="optional" if not config.SETTINGS.cache.tls_insecure else "none",
            ssl_check_hostname=not config.SETTINGS.cache.tls_insecure,
            ssl_ca_certs=config.SETTINGS.cache.tls_ca_file,
        )

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

    async def set(self, key: str, value: str, expires: KVTTL | None = None, not_exists: bool = False) -> bool | None:
        return await self.connection.set(name=key, value=value, ex=expires.value if expires else None, nx=not_exists)

    @classmethod
    async def new(cls) -> RedisCache:
        return cls()
