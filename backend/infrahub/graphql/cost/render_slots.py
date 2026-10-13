from __future__ import annotations

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from prefect.logging import get_run_logger

from infrahub import config
from infrahub.worker import WORKER_IDENTITY
from infrahub.workers.dependencies import get_cache

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from infrahub.services.adapters.cache import InfrahubCache

RENDER_SLOT_KEY_TEMPLATE = "graphql_cost:high_cost_render:slot:{index}"
RENDER_SLOT_TTL_SECONDS = 3600
"""A slot whose holder stopped without releasing it is free again after this time."""

RENDER_SLOT_POLL_SECONDS = 1.0

SLOT_TAKEN_MESSAGE = "Took the high-cost render slot"
SLOT_RELEASED_MESSAGE = "Released the high-cost render slot"


class RenderSlots:
    """At most `size` holders at a time across every process, through keys of the cache that expire."""

    def __init__(
        self,
        cache: InfrahubCache,
        size: int,
        ttl: int = RENDER_SLOT_TTL_SECONDS,
        poll_interval: float = RENDER_SLOT_POLL_SECONDS,
    ) -> None:
        self.cache = cache
        self.size = size
        self.ttl = ttl
        self.poll_interval = poll_interval

    @asynccontextmanager
    async def hold(self) -> AsyncGenerator[int]:
        """Wait for a free slot and hold it until the block ends. Yields the index of the slot."""
        token = f"{WORKER_IDENTITY}::{uuid.uuid4()}"
        index = await self._acquire(token=token)
        try:
            yield index
        finally:
            await self._release(index=index, token=token)

    async def _acquire(self, token: str) -> int:
        while True:
            for index in range(self.size):
                key = RENDER_SLOT_KEY_TEMPLATE.format(index=index)
                if await self.cache.set(key=key, value=token, expires=self.ttl, not_exists=True):
                    return index
            await asyncio.sleep(self.poll_interval)

    async def _release(self, index: int, token: str) -> None:
        key = RENDER_SLOT_KEY_TEMPLATE.format(index=index)
        # After the expiry another render may hold the slot under its own token.
        if await self.cache.get(key=key) == token:
            await self.cache.delete(key=key)


@asynccontextmanager
async def high_cost_render_slot(high_cost: bool) -> AsyncGenerator[None]:
    """Hold a slot of the high-cost renders for a high-cost render, and nothing for another render.

    Logs to the run when it takes the slot and when it releases it.
    """
    if not high_cost or not config.SETTINGS.graphql_cost.limit_high_cost_renders:
        yield
        return
    log = get_run_logger()
    slots = RenderSlots(cache=await get_cache(), size=config.SETTINGS.graphql_cost.high_cost_renders_at_once)
    started = time.monotonic()
    async with slots.hold() as index:
        log.info(f"{SLOT_TAKEN_MESSAGE} {index}, after waiting {time.monotonic() - started:.1f} seconds")
        try:
            yield
        finally:
            log.info(f"{SLOT_RELEASED_MESSAGE} {index}")
