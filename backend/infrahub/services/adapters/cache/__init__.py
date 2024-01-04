from typing import List, Optional


class InfrahubCache:
    """Base class for caching services"""

    async def delete(self, key: str) -> None:
        """Delete a key from the cache."""
        raise NotImplementedError()

    async def get(self, key: str) -> Optional[str]:
        """Retrieve a value from the cache."""
        raise NotImplementedError()

    async def list_keys(self, filter_pattern: str) -> List[str]:
        """Return a list of active keys that match the provided filter."""
        raise NotImplementedError()

    async def set(
        self, key: str, value: str, expires: Optional[int] = None, not_exists: bool = False
    ) -> Optional[bool]:
        """Set a value in the cache."""
        raise NotImplementedError()
