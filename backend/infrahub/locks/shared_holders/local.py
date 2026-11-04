from __future__ import annotations

import time
from typing import TYPE_CHECKING

from .interface import SharedHolderStore

if TYPE_CHECKING:
    from collections.abc import Callable


class LocalSharedHolderStore(SharedHolderStore):
    """Keeps the holders in this process, for locks no other process can take."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._expiries: dict[str, dict[str, float]] = {}

    async def add(self, key: str, holder: str, token: str, ttl_seconds: int) -> None:  # noqa: ARG002
        self._expiries.setdefault(key, {})[holder] = self._clock() + ttl_seconds

    async def remove(self, key: str, holder: str) -> None:
        holders = self._expiries.get(key, {})
        holders.pop(holder, None)
        if not holders:
            self._expiries.pop(key, None)

    async def has_holders(self, key: str) -> bool:
        now = self._clock()
        holders = {holder: expiry for holder, expiry in self._expiries.get(key, {}).items() if expiry > now}
        if holders:
            self._expiries[key] = holders
        else:
            self._expiries.pop(key, None)
        return bool(holders)
