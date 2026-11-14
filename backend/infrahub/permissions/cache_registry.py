from __future__ import annotations

from infrahub import config

from .cache import AccountPermissionCache

# Far above the number of (account, branch) pairs active at once; it only bounds memory.
ACCOUNT_PERMISSION_CACHE_MAX_ENTRIES = 4096

_account_permission_cache: AccountPermissionCache | None = None


def get_account_permission_cache() -> AccountPermissionCache:
    """Return the process-global permission cache, building it on first use and whenever the configured TTL changes."""
    global _account_permission_cache
    ttl_seconds = config.SETTINGS.security.auth_cache_ttl_seconds
    if _account_permission_cache is None or _account_permission_cache.ttl_seconds != ttl_seconds:
        _account_permission_cache = AccountPermissionCache(
            ttl_seconds=ttl_seconds, max_entries=ACCOUNT_PERMISSION_CACHE_MAX_ENTRIES
        )
    return _account_permission_cache


def reset_account_permission_cache() -> None:
    global _account_permission_cache
    _account_permission_cache = None
