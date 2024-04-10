import re
from typing import Optional

from infrahub.services.adapters.cache import InfrahubCache


class MemoryCache(InfrahubCache):
    def __init__(self) -> None:
        self.storage: dict[str, str] = {}

    async def delete(self, key: str) -> None:
        self.storage.pop(key, None)

    async def get(self, key: str) -> Optional[str]:
        return self.storage.get(key)

    async def get_values(self, keys: list[str]) -> list[Optional[str]]:
        return [await self.get(key) for key in keys]

    async def list_keys(self, filter_pattern: str) -> list[str]:
        regex_pattern = f'^{filter_pattern.replace("*", ".*").replace("?", ".")}$'
        compiled_pattern = re.compile(regex_pattern)
        return [key for key in self.storage.keys() if compiled_pattern.match(key)]

    async def set(
        self, key: str, value: str, expires: Optional[int] = None, not_exists: bool = False
    ) -> Optional[bool]:
        self.storage[key] = value
        return True
