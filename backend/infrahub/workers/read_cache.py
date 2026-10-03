from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Hashable


@dataclass(frozen=True)
class _CachedModel[ModelT: BaseModel]:
    model: ModelT
    expires_at: float


class ExpiringModelCache[KeyT: Hashable, ModelT: BaseModel]:
    """Serve repeated reads of the same model from memory, reaching the source at most once per key until it expires."""

    def __init__(
        self, read: Callable[[KeyT], Awaitable[ModelT]], ttl_seconds: float, clock: Callable[[], float]
    ) -> None:
        self._read = read
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._entries: dict[KeyT, _CachedModel[ModelT]] = {}
        self._locks: dict[KeyT, asyncio.Lock] = {}

    async def read(self, key: KeyT) -> ModelT:
        """Return a copy of the model stored under `key`, reading it from the source when missing or expired.

        A failed read is not cached: whatever the source raises reaches the caller, and the next read retries.
        """
        # Concurrent misses on one key wait for a single read instead of each reaching the source.
        async with self._locks.setdefault(key, asyncio.Lock()):
            entry = self._entries.get(key)
            if entry is None or self._clock() >= entry.expires_at:
                model = await self._read(key)
                entry = _CachedModel(model=model, expires_at=self._clock() + self._ttl_seconds)
                self._entries[key] = entry
        # A caller may modify the model it receives, which must not leak into later reads.
        return entry.model.model_copy(deep=True)
