"""Tunables for the read-only repository refs check."""

from __future__ import annotations

from types import MappingProxyType
from typing import Final, Mapping

REFS_CHECK_TIMEOUT_SECONDS: Final = 120
"""Wall-clock ceiling for reading one repository's remote refs. Convergence is not covered by it."""

REFS_CHECK_CLAIM_MARGIN_SECONDS: Final = 60
"""Added to the listing ceiling so a claim outlives the step that can wait on an unresponsive host."""

REFS_CHECK_GIT_KILL_MARGIN_SECONDS: Final = 10
"""How much sooner the listing subprocess is killed than the wall-clock ceiling above it."""

REFS_CHECK_FETCH_TIMEOUT_SECONDS: Final = 900
"""Ceiling on the transfer, enforced by killing the git process. Generous: a first transfer of a
large repository is legitimately slow."""

REFS_CHECK_CLAIM_TTL_SECONDS: Final = REFS_CHECK_TIMEOUT_SECONDS + REFS_CHECK_CLAIM_MARGIN_SECONDS

REFS_CHECK_CONCURRENCY: Final = 5
"""How many repositories one cycle contacts at a time."""

REFS_CHECK_RETRY_SECONDS: Final = 300
"""How soon a failed repository becomes due again. Clamped to the configured interval when that is
shorter, so a failure is never made to wait longer than a healthy check would."""

# git applies no network timeout of its own. These end an HTTP transfer that has stalled below a
# trickle; every transport, SSH included, is bounded instead by the kill timeout git is given.
REMOTE_TRANSPORT_ENVIRONMENT: Final[Mapping[str, str]] = MappingProxyType(
    {"GIT_HTTP_LOW_SPEED_LIMIT": "1000", "GIT_HTTP_LOW_SPEED_TIME": "20"}
)
