from __future__ import annotations

import hashlib
import time
from typing import TYPE_CHECKING

from cachetools import TTLCache

if TYPE_CHECKING:
    from collections.abc import Callable


class AccountTokenCache:
    """Remember which account an API token resolved to, for a bounded time.

    Entries are keyed by a SHA-256 digest of the token, so the cache never holds a token value.
    A TTL of zero disables the cache: every lookup misses and nothing is stored.
    """

    def __init__(self, *, ttl_seconds: float, max_entries: int, clock: Callable[[], float] = time.monotonic) -> None:
        self._ttl_seconds = ttl_seconds
        self._entries: TTLCache[str, str] | None = (
            TTLCache(maxsize=max_entries, ttl=ttl_seconds, timer=clock) if ttl_seconds > 0 else None
        )

    @property
    def ttl_seconds(self) -> float:
        return self._ttl_seconds

    @property
    def enabled(self) -> bool:
        return self._entries is not None

    def get_account_id(self, token: str) -> str | None:
        if self._entries is None:
            return None
        return self._entries.get(self._digest(token=token))

    def set_account_id(self, token: str, account_id: str) -> None:
        if self._entries is None:
            return
        self._entries[self._digest(token=token)] = account_id

    def clear(self) -> None:
        if self._entries is not None:
            self._entries.clear()

    def _digest(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
