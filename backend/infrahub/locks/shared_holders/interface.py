from __future__ import annotations

from abc import ABC, abstractmethod


class SharedHolderStore(ABC):
    """Records the holders of each lock taken in shared mode, under one key per lock."""

    @abstractmethod
    async def add(self, key: str, holder: str, token: str, ttl_seconds: int) -> None:
        """Record `holder` of the lock at `key` with `token`, or renew it, until `ttl_seconds` pass without another call."""
        raise NotImplementedError()

    @abstractmethod
    async def remove(self, key: str, holder: str) -> None:
        """Forget `holder` of the lock at `key`."""
        raise NotImplementedError()

    @abstractmethod
    async def has_holders(self, key: str) -> bool:
        """Return whether a holder whose record has not expired is recorded for the lock at `key`."""
        raise NotImplementedError()
