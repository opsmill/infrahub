from __future__ import annotations

from infrahub import config

from .token_cache import AccountTokenCache

# Far above the number of API tokens a deployment uses at once; it only bounds memory.
ACCOUNT_TOKEN_CACHE_MAX_ENTRIES = 4096

_account_token_cache: AccountTokenCache | None = None


def get_account_token_cache() -> AccountTokenCache:
    """Return the process-global token cache, building it on first use and whenever the configured TTL changes."""
    global _account_token_cache
    ttl_seconds = config.SETTINGS.security.auth_cache_ttl_seconds
    if _account_token_cache is None or _account_token_cache.ttl_seconds != ttl_seconds:
        _account_token_cache = AccountTokenCache(ttl_seconds=ttl_seconds, max_entries=ACCOUNT_TOKEN_CACHE_MAX_ENTRIES)
    return _account_token_cache


def reset_account_token_cache() -> None:
    global _account_token_cache
    _account_token_cache = None
