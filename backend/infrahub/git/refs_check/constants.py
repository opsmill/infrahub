"""Tunables for the read-only repository refs check."""

from __future__ import annotations

from types import MappingProxyType
from typing import Final, Mapping

REFS_CHECK_TIMEOUT_SECONDS: Final = 120
"""Wall-clock ceiling for reading one repository's remote refs.

Convergence is deliberately outside it: that step holds the repository lock, which has no expiry,
so abandoning a run part-way through releasing it would block the repository indefinitely.
"""

REFS_CHECK_CLAIM_MARGIN_SECONDS: Final = 60
"""Added to the listing ceiling so a claim outlives the step that can wait on an unresponsive host."""

REFS_CHECK_CLAIM_TTL_SECONDS: Final = REFS_CHECK_TIMEOUT_SECONDS + REFS_CHECK_CLAIM_MARGIN_SECONDS

REFS_CHECK_CONCURRENCY: Final = 5
"""How many repositories one cycle contacts at a time."""

REFS_CHECK_RETRY_SECONDS: Final = 300
"""How soon a failed repository becomes due again.

Sooner than a full interval, because a failure is usually transient; later than the next tick of
the schedule, because a permanent one would otherwise be retried every minute forever.
"""

# git applies no network timeout of its own. These bind the HTTP transport only, so an SSH remote
# is still bounded by the caller's own ceiling rather than by these.
REMOTE_TRANSPORT_ENVIRONMENT: Final[Mapping[str, str]] = MappingProxyType(
    {"GIT_HTTP_LOW_SPEED_LIMIT": "1000", "GIT_HTTP_LOW_SPEED_TIME": "20"}
)
