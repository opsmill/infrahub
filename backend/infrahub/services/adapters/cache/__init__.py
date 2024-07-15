from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from infrahub.message_bus.types import KVTTL
    from infrahub.services import InfrahubServices


class InfrahubCache:
    """Base class for caching services"""

    async def initialize(self, service: InfrahubServices) -> None:
        """Initialize the cache"""

    async def delete(self, key: str) -> None:
        """Delete a key from the cache."""
        raise NotImplementedError()

    async def get(self, key: str) -> Optional[str]:
        """Retrieve a value from the cache."""
        raise NotImplementedError()

    async def get_values(self, keys: list[str]) -> list[Optional[str]]:
        """Return a list the values for requested keys."""
        raise NotImplementedError()

    async def list_keys(self, filter_pattern: str) -> list[str]:
        """Return a list of active keys that match the provided filter."""
        raise NotImplementedError()

    async def set(
        self, key: str, value: str, expires: Optional[KVTTL] = None, not_exists: bool = False
    ) -> Optional[bool]:
        """Set a value in the cache."""
        raise NotImplementedError()
