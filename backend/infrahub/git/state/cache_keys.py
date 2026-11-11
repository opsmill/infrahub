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

REFS_CHECK_LISTED_TTL_SECONDS = 30 * 24 * 60 * 60
"""Every check writes the value again, so it lapses only for a ref no check has listed for this long,
such as one of a deleted repository; a lapsed value costs one repeated broadcast."""

ACTIVITY_RUN_TTL_SECONDS = 300
"""Several renewal intervals, because a synchronous git fetch blocks the event loop and can delay a
renewal by more than a minute; a worker that is killed leaves a record that expires within this time."""

ACTIVITY_RUN_RENEW_SECONDS = 60

ACTIVITY_LAST_RUN_TTL_SECONDS = 30 * 24 * 60 * 60
"""Bounded so the last run of a deleted repository does not linger."""


def warm_up_key(repository_id: str) -> str:
    return f"{CACHE_KEY_PREFIX}:warmup:{repository_id}"


def refs_check_due_key(repository_id: str) -> str:
    return f"{CACHE_KEY_PREFIX}:refs_check:due:{repository_id}"


def refs_check_running_key(repository_id: str) -> str:
    return f"{CACHE_KEY_PREFIX}:refs_check:running:{repository_id}"


def refs_check_last_key(repository_id: str) -> str:
    return f"{CACHE_KEY_PREFIX}:refs_check:last:{repository_id}"


def refs_check_listed_key(repository_id: str, ref: str) -> str:
    return f"{CACHE_KEY_PREFIX}:refs_check:listed:{repository_id}:{ref}"


def activity_run_key(repository_id: str, run_id: str) -> str:
    return f"{CACHE_KEY_PREFIX}:activity:run:{repository_id}:{run_id}"


def activity_run_pattern(repository_id: str) -> str:
    """Return the pattern that matches every run record of one repository."""
    return f"{CACHE_KEY_PREFIX}:activity:run:{repository_id}:*"


def activity_last_run_key(repository_id: str, operation: str) -> str:
    return f"{CACHE_KEY_PREFIX}:activity:last:{repository_id}:{operation}"
