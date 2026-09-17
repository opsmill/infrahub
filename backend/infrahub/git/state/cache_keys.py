"""Cache keys shared by the API resolvers and the git worker flows.

The API server and the workers write and read these keys from different processes, so the string
formats live here rather than at either end.
"""

from __future__ import annotations

from infrahub.message_bus.types import KVTTL

CACHE_KEY_PREFIX = "git"

WARM_UP_TTL = KVTTL.ONE_MINUTE
"""Long enough to collapse the triggers of one burst of reads, short enough that a warm-up which
never starts does not suppress the next attempt."""

REFS_CHECK_LAST_TTL_SECONDS = 30 * 24 * 60 * 60
"""Bounded so a deleted repository's key does not linger; a check time older than this reads as
absent rather than stale."""


def warm_up_key(repository_id: str) -> str:
    return f"{CACHE_KEY_PREFIX}:warmup:{repository_id}"


def refs_check_due_key(repository_id: str) -> str:
    return f"{CACHE_KEY_PREFIX}:refs_check:due:{repository_id}"


def refs_check_running_key(repository_id: str) -> str:
    return f"{CACHE_KEY_PREFIX}:refs_check:running:{repository_id}"


def refs_check_last_key(repository_id: str) -> str:
    return f"{CACHE_KEY_PREFIX}:refs_check:last:{repository_id}"
