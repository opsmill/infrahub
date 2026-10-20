from __future__ import annotations

from infrahub.git.writeback.constants import (
    BARRIER_STATE_READ_DELAYS_SECONDS,
    DELIVERY_RETRIES,
    DELIVERY_RETRY_DELAYS_SECONDS,
    ENQUEUE_RETRY_DELAYS_SECONDS,
    FETCH_TIMEOUT_SECONDS,
    NARROWED_HOLD_TTL_SECONDS,
    PUSH_TIMEOUT_SECONDS,
    STATE_LOCK_TTL_SECONDS,
)


def test_narrowed_hold_outlives_a_retry_chain_whose_fetches_and_pushes_end_at_their_limits() -> None:
    attempts = DELIVERY_RETRIES + 1
    chain_seconds = sum(DELIVERY_RETRY_DELAYS_SECONDS) + attempts * (FETCH_TIMEOUT_SECONDS + PUSH_TIMEOUT_SECONDS)

    assert chain_seconds < NARROWED_HOLD_TTL_SECONDS


def test_the_last_retry_of_a_state_call_starts_after_the_state_lock_of_a_dead_worker_expired() -> None:
    assert sum(ENQUEUE_RETRY_DELAYS_SECONDS) >= STATE_LOCK_TTL_SECONDS
    assert sum(BARRIER_STATE_READ_DELAYS_SECONDS) >= STATE_LOCK_TTL_SECONDS
