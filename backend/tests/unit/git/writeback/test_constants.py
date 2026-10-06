from __future__ import annotations

from infrahub.git.writeback.constants import (
    DELIVERY_RETRIES,
    DELIVERY_RETRY_DELAYS_SECONDS,
    FETCH_TIMEOUT_SECONDS,
    NARROWED_HOLD_TTL_SECONDS,
    PUSH_TIMEOUT_SECONDS,
)

IMPORT_AND_QUEUE_UPDATE_MARGIN_SECONDS = 10 * 60


def test_narrowed_hold_lives_for_a_whole_automatic_retry_chain_plus_the_import_margin() -> None:
    attempts = DELIVERY_RETRIES + 1
    retry_chain_seconds = sum(DELIVERY_RETRY_DELAYS_SECONDS) + attempts * (FETCH_TIMEOUT_SECONDS + PUSH_TIMEOUT_SECONDS)

    assert retry_chain_seconds + IMPORT_AND_QUEUE_UPDATE_MARGIN_SECONDS == NARROWED_HOLD_TTL_SECONDS
