from __future__ import annotations

import time
from fnmatch import fnmatchcase
from typing import TYPE_CHECKING

from . import SharedHolderStore

if TYPE_CHECKING:
    from collections.abc import Callable


class LocalSharedHolderStore(SharedHolderStore):
    """Keeps the holders in this process, for locks no other process can take."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._expiries: dict[str, float] = {}

    async def add(self, key: str, token: str, ttl_seconds: int) -> None:  # noqa: ARG002
        self._expiries[key] = self._clock() + ttl_seconds

    async def remove(self, key: str) -> None:
        self._expiries.pop(key, None)

    async def has_holders(self, pattern: str) -> bool:
        now = self._clock()
        self._expiries = {key: expiry for key, expiry in self._expiries.items() if expiry > now}
        return any(fnmatchcase(key, pattern) for key in self._expiries)
