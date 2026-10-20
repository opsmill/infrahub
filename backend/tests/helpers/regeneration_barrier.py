"""Build the regeneration barrier that a recompute or a merge follow-up consults, for a test."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from infrahub.core.merge.regeneration_barrier import NarrowedHoldCache, RegenerationBarrier
from infrahub.git.writeback.constants import NARROWED_HOLD_MAX_BYTES, NARROWED_HOLD_TTL_SECONDS
from tests.adapters.cache import MemoryCache

if TYPE_CHECKING:
    from infrahub.git.writeback.ports import DeliveryStatePort


def regeneration_barrier(*, state: DeliveryStatePort, default_branch_name: str) -> RegenerationBarrier:
    """Return a barrier over `state` that keeps its narrowed requests in memory."""
    return RegenerationBarrier(
        state=state,
        narrowed=NarrowedHoldCache(
            cache=MemoryCache(), ttl_seconds=NARROWED_HOLD_TTL_SECONDS, max_bytes=NARROWED_HOLD_MAX_BYTES
        ),
        default_branch_name=default_branch_name,
        sleep=asyncio.sleep,
    )
