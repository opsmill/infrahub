from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from infrahub.message_bus.types import KVTTL


class InfrahubCache(ABC):
    """Base class for caching services"""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a key from the cache."""
        raise NotImplementedError()

    @abstractmethod
    async def get(self, key: str) -> Optional[str]:
        """Retrieve a value from the cache."""
        raise NotImplementedError()

    @abstractmethod
    async def get_values(self, keys: list[str]) -> list[Optional[str]]:
        """Return a list the values for requested keys."""
        raise NotImplementedError()

    @abstractmethod
    async def list_keys(self, filter_pattern: str) -> list[str]:
        """Return a list of active keys that match the provided filter."""
        raise NotImplementedError()

    @abstractmethod
    async def set(
        self, key: str, value: str, expires: Optional[KVTTL] = None, not_exists: bool = False
    ) -> Optional[bool]:
        """Set a value in the cache."""
        raise NotImplementedError()
