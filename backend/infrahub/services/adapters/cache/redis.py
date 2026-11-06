from __future__ import annotations

from prefect_redis.connection import aclose_redis_client
from redis.exceptions import ResponseError

from infrahub import config
from infrahub.exceptions import DependencyUnhealthyError
from infrahub.message_bus.types import KVTTL
from infrahub.redis_connection import build_redis_connection
from infrahub.services.adapters.cache import InfrahubCache
from infrahub.worker import WORKER_IDENTITY


class RedisCache(InfrahubCache):
    def __init__(self) -> None:
        self.connection = build_redis_connection(config.SETTINGS.cache)
        # A client of its own without retries, so a failing cache is reported with its error instead of a timeout of
        # the retries; it connects only when a health check runs.
        self._health_check_connection = build_redis_connection(config.SETTINGS.cache, retries=0)

    async def delete(self, key: str) -> None:
        await self.connection.delete(key)

    async def get(self, key: str) -> str | None:
        value = await self.connection.get(name=key)
        # redis-py types a response as bytes or str because a connection can decode responses
        # itself; this one does not, so the values come back as bytes.
        if isinstance(value, bytes):
            return value.decode()
        return value

    async def get_values(self, keys: list[str]) -> list[str | None]:
        values = await self.connection.mget(keys=keys)
        return [value.decode() if isinstance(value, bytes) else value for value in values]

    async def list_keys(self, filter_pattern: str) -> list[str]:
        cursor = 0
        has_remaining_keys = True
        keys = []
        while has_remaining_keys:
            cursor, scanned_keys = await self.connection.scan(cursor=cursor, match=filter_pattern, count=100)
            keys.extend(scanned_keys)
            if cursor == 0:
                has_remaining_keys = False

        return [key.decode() if isinstance(key, bytes) else key for key in keys]

    async def set(
        self, key: str, value: str, expires: KVTTL | int | None = None, not_exists: bool = False
    ) -> bool | None:
        # redis-py cannot encode an IntEnum (e.g. KVTTL) directly, so coerce the TTL to a plain int.
        ex = int(expires) if expires else None
        result = await self.connection.set(name=key, value=value, ex=ex, nx=not_exists)
        # redis-py also types the response of the `get=` option (the previous value); this call never
        # asks for it, so the response is True on success and None when `nx` finds the key set.
        return bool(result) if result is not None else None

    @classmethod
    async def new(cls) -> RedisCache:
        return cls()

    async def close_connection(self) -> None:
        await aclose_redis_client(self.connection)
        await aclose_redis_client(self._health_check_connection)

    async def check_health(self) -> None:
        # A write, because Redis keeps answering PING while it refuses writes (persistence failing, memory full, replica).
        try:
            await self._health_check_connection.set(
                name=f"health:check:{WORKER_IDENTITY}", value="1", ex=int(KVTTL.ONE_MINUTE)
            )
        except ResponseError as exc:
            raise DependencyUnhealthyError(message="The cache refused a write") from exc
