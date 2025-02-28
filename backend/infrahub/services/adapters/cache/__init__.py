from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.message_bus.types import KVTTL


class InfrahubCache(ABC):
    """Base class for caching services"""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a key from the cache."""
        raise NotImplementedError()

    @abstractmethod
    async def get(self, key: str) -> str | None:
        """Retrieve a value from the cache."""
        raise NotImplementedError()

    @abstractmethod
    async def get_values(self, keys: list[str]) -> list[str | None]:
        """Return a list the values for requested keys."""
        raise NotImplementedError()

    @abstractmethod
    async def list_keys(self, filter_pattern: str) -> list[str]:
        """Return a list of active keys that match the provided filter."""
        raise NotImplementedError()

    @abstractmethod
    async def set(self, key: str, value: str, expires: KVTTL | None = None, not_exists: bool = False) -> bool | None:
        """Set a value in the cache."""
        raise NotImplementedError()
