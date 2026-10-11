from __future__ import annotations

import asyncio

from infrahub.graphql.cost.render_slots import RENDER_SLOT_KEY_TEMPLATE, RenderSlots
from tests.adapters.cache import MemoryCache


class ExclusiveMemoryCache(MemoryCache):
    """Refuses to replace a key when asked to set it only if it does not exist, as the Redis and NATS caches do."""

    async def set(self, key: str, value: str, expires: int | None = None, not_exists: bool = False) -> bool | None:
        if not_exists and key in self.storage:
            return False
        return await super().set(key=key, value=value, expires=expires, not_exists=not_exists)


async def test_a_holder_waits_until_the_only_slot_is_released() -> None:
    slots = RenderSlots(cache=ExclusiveMemoryCache(), size=1, poll_interval=0.01)
    events: list[str] = []
    first_holds = asyncio.Event()
    release_first = asyncio.Event()

    async def first() -> None:
        async with slots.hold():
            events.append("first holds")
            first_holds.set()
            await release_first.wait()
            events.append("first releases")

    async def second() -> None:
        await first_holds.wait()
        async with slots.hold():
            events.append("second holds")

    second_task = asyncio.create_task(second())
    first_task = asyncio.create_task(first())
    await first_holds.wait()
    await asyncio.sleep(0.05)
    assert events == ["first holds"]

    release_first.set()
    await asyncio.gather(first_task, second_task)
    assert events == ["first holds", "first releases", "second holds"]


async def test_holders_use_distinct_slots_up_to_the_size() -> None:
    slots = RenderSlots(cache=ExclusiveMemoryCache(), size=2, poll_interval=0.01)

    async with slots.hold() as first, slots.hold() as second:
        assert {first, second} == {0, 1}


async def test_release_keeps_a_slot_that_another_holder_took_after_the_expiry() -> None:
    cache = ExclusiveMemoryCache()
    slots = RenderSlots(cache=cache, size=1, poll_interval=0.01)
    key = RENDER_SLOT_KEY_TEMPLATE.format(index=0)

    async with slots.hold():
        await cache.set(key=key, value="another-holder")

    assert await cache.get(key=key) == "another-holder"


async def test_release_frees_the_slot() -> None:
    cache = ExclusiveMemoryCache()
    slots = RenderSlots(cache=cache, size=1, poll_interval=0.01)

    async with slots.hold():
        pass

    assert await cache.get(key=RENDER_SLOT_KEY_TEMPLATE.format(index=0)) is None
