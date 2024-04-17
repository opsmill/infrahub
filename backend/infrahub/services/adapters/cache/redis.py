from typing import List, Optional

import redis.asyncio as redis

from infrahub import config
from infrahub.message_bus.types import KVTTL
from infrahub.services import InfrahubServices
from infrahub.services.adapters.cache import InfrahubCache


class RedisCache(InfrahubCache):
    def __init__(self) -> None:
        self.connection = redis.Redis(
            host=config.SETTINGS.cache.address,
            port=config.SETTINGS.cache.service_port,
            db=config.SETTINGS.cache.database,
        )

    async def initialize(self, service: InfrahubServices) -> None:
        pass

    async def delete(self, key: str) -> None:
        await self.connection.delete(key)

    async def get(self, key: str) -> Optional[str]:
        value = await self.connection.get(name=key)
        if value is not None:
            return value.decode()
        return None

    async def get_values(self, keys: list[str]) -> list[Optional[str]]:
        values = await self.connection.mget(keys=keys)
        return [value.decode() if value is not None else value for value in values]

    async def list_keys(self, filter_pattern: str) -> List[str]:
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
        self, key: str, value: str, expires: Optional[KVTTL] = None, not_exists: bool = False
    ) -> Optional[bool]:
        return await self.connection.set(name=key, value=value, ex=expires.value if expires else None, nx=not_exists)
