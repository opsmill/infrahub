from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from prefect_redis.connection import aclose_redis_client

from infrahub import config
from infrahub.lock import LOCK_PREFIX, InfrahubLock
from infrahub.redis_connection import build_redis_connection

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    import redis.asyncio as redis

# More locks than the 100 connections redis-py 8 gives a pool that is not sized explicitly.
CONCURRENT_LOCKS = 150
# While Redis is paused, every command sent keeps its connection until Redis answers.
PAUSE_MILLISECONDS = 500


@pytest.fixture
async def client(redis: dict[int, int] | None) -> AsyncGenerator[redis.Redis, None]:
    client = build_redis_connection(config.SETTINGS.cache)
    yield client
    await aclose_redis_client(client)


async def test_locks_acquired_at_once_each_get_a_connection(client: redis.Redis) -> None:
    """Every lock of a burst larger than redis-py's default pool is acquired and released."""
    prefix = f"burst-{uuid4()}"
    locks = [
        InfrahubLock(name=f"{prefix}-{index}", connection=client, metrics=False) for index in range(CONCURRENT_LOCKS)
    ]

    async def hold(lock: InfrahubLock) -> bool:
        await lock.acquire()
        held = await lock.locked()
        await lock.release()
        return held

    await client.client_pause(timeout=PAUSE_MILLISECONDS)
    held = await asyncio.gather(*(hold(lock) for lock in locks))

    assert held == [True] * CONCURRENT_LOCKS
    # The pool keeps the connections it opened, so the burst needed one per lock at the same time.
    assert len(await client.client_list()) >= CONCURRENT_LOCKS
    assert [key async for key in client.scan_iter(match=f"{LOCK_PREFIX}.{prefix}-*")] == []
