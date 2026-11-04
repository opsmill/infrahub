from __future__ import annotations

from abc import ABC, abstractmethod


class SharedHolderStore(ABC):
    """Records each holder of a lock taken in shared mode, under the lock's name."""

    @abstractmethod
    async def add(self, key: str, token: str, ttl_seconds: int) -> None:
        """Record a holder at `key`, or renew it, until `ttl_seconds` pass without another call."""
        raise NotImplementedError()

    @abstractmethod
    async def remove(self, key: str) -> None:
        """Forget the holder recorded at `key`."""
        raise NotImplementedError()

    @abstractmethod
    async def has_holders(self, pattern: str) -> bool:
        """Return whether a holder is recorded at a key matching `pattern`, where `*` matches any suffix."""
        raise NotImplementedError()
