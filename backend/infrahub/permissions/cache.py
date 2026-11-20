from __future__ import annotations

import time
from typing import TYPE_CHECKING

from cachetools import TTLCache

if TYPE_CHECKING:
    from collections.abc import Callable

    from infrahub.permissions.types import AssignedPermissions


class AccountPermissionCache:
    """Remember the permissions loaded for an account on a branch, for a bounded time.

    Lookups return copies, so a caller cannot change what later lookups read.
    A TTL of zero disables the cache: every lookup misses and nothing is stored.
    """

    def __init__(self, *, ttl_seconds: float, max_entries: int, clock: Callable[[], float] = time.monotonic) -> None:
        self._ttl_seconds = ttl_seconds
        self._entries: TTLCache[tuple[str, str], AssignedPermissions] | None = (
            TTLCache(maxsize=max_entries, ttl=ttl_seconds, timer=clock) if ttl_seconds > 0 else None
        )

    @property
    def ttl_seconds(self) -> float:
        return self._ttl_seconds

    @property
    def enabled(self) -> bool:
        return self._entries is not None

    def get(self, account_id: str, branch_name: str) -> AssignedPermissions | None:
        if self._entries is None:
            return None
        permissions = self._entries.get((account_id, branch_name))
        if permissions is None:
            return None
        return self._copy(permissions=permissions)

    def set(self, account_id: str, branch_name: str, permissions: AssignedPermissions) -> None:
        if self._entries is None:
            return
        self._entries[account_id, branch_name] = self._copy(permissions=permissions)

    def clear(self) -> None:
        if self._entries is not None:
            self._entries.clear()

    def _copy(self, permissions: AssignedPermissions) -> AssignedPermissions:
        return {
            "global_permissions": list(permissions["global_permissions"]),
            "object_permissions": list(permissions["object_permissions"]),
        }
