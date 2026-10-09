"""Tunables for the read-only repository refs check."""

from __future__ import annotations

from typing import Final

REFS_CHECK_TIMEOUT_SECONDS: Final = 120
"""Wall-clock ceiling for reading one repository's remote refs and the heads last listed for them.
Convergence is not covered by it."""

REFS_CHECK_CLAIM_MARGIN_SECONDS: Final = 60
"""Added to the ceiling above so a claim outlives the steps that can wait on a remote or the cache."""

REFS_CHECK_GIT_KILL_MARGIN_SECONDS: Final = 10
"""How much sooner the listing subprocess is killed than the wall-clock ceiling above it."""

REFS_CHECK_CLAIM_TTL_SECONDS: Final = REFS_CHECK_TIMEOUT_SECONDS + REFS_CHECK_CLAIM_MARGIN_SECONDS

REFS_CHECK_CONCURRENCY: Final = 5
"""How many repositories one cycle contacts at a time."""

REFS_CHECK_RETRY_SECONDS: Final = 300
"""How soon a failed repository becomes due again. Clamped to the configured interval when that is
shorter, so a failure is never made to wait longer than a healthy check would."""
