import re
from dataclasses import dataclass

from infrahub.message_bus.types import KVTTL
from infrahub.services.adapters.cache import InfrahubCache


class MemoryCache(InfrahubCache):
    def __init__(self) -> None:
        self.storage: dict[str, str] = {}

    async def delete(self, key: str) -> None:
        self.storage.pop(key, None)

    async def get(self, key: str) -> str | None:
        return self.storage.get(key)

    async def get_values(self, keys: list[str]) -> list[str | None]:
        return [await self.get(key) for key in keys]

    async def list_keys(self, filter_pattern: str) -> list[str]:
        regex_pattern = f"^{filter_pattern.replace('*', '.*').replace('?', '.')}$"
        compiled_pattern = re.compile(regex_pattern)
        return [key for key in self.storage.keys() if compiled_pattern.match(key)]

    async def set(self, key: str, value: str, expires: int | None = None, not_exists: bool = False) -> bool | None:
        self.storage[key] = value
        return True

    async def close_connection(self) -> None: ...


class ClaimAwareCache(InfrahubCache):
    """In-memory cache that honours ``not_exists`` and records the expiry each key was written with."""

    def __init__(self) -> None:
        self.storage: dict[str, str] = {}
        self.expires: dict[str, int | None] = {}
        self.deleted: list[str] = []

    async def delete(self, key: str) -> None:
        self.storage.pop(key, None)
        self.expires.pop(key, None)
        self.deleted.append(key)

    async def get(self, key: str) -> str | None:
        return self.storage.get(key)

    async def get_values(self, keys: list[str]) -> list[str | None]:
        return [self.storage.get(key) for key in keys]

    async def list_keys(self, filter_pattern: str) -> list[str]:
        regex_pattern = f"^{filter_pattern.replace('*', '.*').replace('?', '.')}$"
        compiled_pattern = re.compile(regex_pattern)
        return [key for key in self.storage if compiled_pattern.match(key)]

    async def set(self, key: str, value: str, expires: int | None = None, not_exists: bool = False) -> bool | None:
        if not_exists and key in self.storage:
            return False
        self.storage[key] = value
        self.expires[key] = expires
        return True

    async def close_connection(self) -> None: ...


@dataclass(frozen=True)
class CacheSetCall:
    key: str
    value: str
    expires: KVTTL | int | None
    not_exists: bool


class RecordingCache(ClaimAwareCache):
    """Records every write in order, on top of honouring ``not_exists``."""

    def __init__(self) -> None:
        super().__init__()
        self.set_calls: list[CacheSetCall] = []

    async def set(
        self, key: str, value: str, expires: KVTTL | int | None = None, not_exists: bool = False
    ) -> bool | None:
        self.set_calls.append(CacheSetCall(key=key, value=value, expires=expires, not_exists=not_exists))
        return await super().set(key=key, value=value, expires=expires, not_exists=not_exists)


class UnreachableCache(InfrahubCache):
    """Simulates an unreachable cache backend by raising on every operation."""

    async def delete(self, key: str) -> None:
        raise ConnectionError("cache unreachable")

    async def get(self, key: str) -> str | None:
        raise ConnectionError("cache unreachable")

    async def get_values(self, keys: list[str]) -> list[str | None]:
        raise ConnectionError("cache unreachable")

    async def list_keys(self, filter_pattern: str) -> list[str]:
        raise ConnectionError("cache unreachable")

    async def set(self, key: str, value: str, expires: int | None = None, not_exists: bool = False) -> bool | None:
        raise ConnectionError("cache unreachable")

    async def close_connection(self) -> None: ...
