import re
from dataclasses import dataclass

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


@dataclass(frozen=True)
class CacheCall:
    operation: str
    keys: tuple[str, ...]
    """The keys the call read or wrote, or the filter pattern of a key listing."""


class RecordingCache(MemoryCache):
    """Memory cache that keeps, in order, every call made to it."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[CacheCall] = []

    def calls_of(self, operation: str) -> list[CacheCall]:
        return [call for call in self.calls if call.operation == operation]

    async def delete(self, key: str) -> None:
        self.calls.append(CacheCall(operation="delete", keys=(key,)))
        self.storage.pop(key, None)

    async def get(self, key: str) -> str | None:
        self.calls.append(CacheCall(operation="get", keys=(key,)))
        return self.storage.get(key)

    async def get_values(self, keys: list[str]) -> list[str | None]:
        self.calls.append(CacheCall(operation="get_values", keys=tuple(keys)))
        return [self.storage.get(key) for key in keys]

    async def list_keys(self, filter_pattern: str) -> list[str]:
        self.calls.append(CacheCall(operation="list_keys", keys=(filter_pattern,)))
        return await super().list_keys(filter_pattern=filter_pattern)

    async def set(self, key: str, value: str, expires: int | None = None, not_exists: bool = False) -> bool | None:
        self.calls.append(CacheCall(operation="set", keys=(key,)))
        self.storage[key] = value
        return True


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
