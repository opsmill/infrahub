from __future__ import annotations

import asyncio

import pytest

from infrahub.tasks.registry import (
    _PROCESS_SCHEMA_REFRESH_LOCK,
    serialize_process_schema_refresh,
)


async def test_serialize_process_schema_refresh_is_mutually_exclusive() -> None:
    # Concurrent callers (one per worker thread sharing a process) must not run the
    # guarded schema reload at the same time on the process-global registry.
    active = 0
    max_active = 0

    async def worker() -> None:
        nonlocal active, max_active
        async with serialize_process_schema_refresh():
            active += 1
            max_active = max(max_active, active)
            # Force an await so overlapping callers would interleave here if the
            # guard did not serialize them.
            await asyncio.sleep(0.02)
            active -= 1

    await asyncio.gather(*(worker() for _ in range(8)))

    assert max_active == 1
    # The lock is free again once every caller is done.
    assert _PROCESS_SCHEMA_REFRESH_LOCK.acquire(blocking=False) is True
    _PROCESS_SCHEMA_REFRESH_LOCK.release()


async def test_serialize_process_schema_refresh_releases_on_error() -> None:
    # The lock must be released when the guarded block raises, otherwise every later
    # refresh in the process would deadlock waiting on it.
    with pytest.raises(RuntimeError, match="boom"):
        async with serialize_process_schema_refresh():
            raise RuntimeError("boom")

    assert _PROCESS_SCHEMA_REFRESH_LOCK.acquire(blocking=False) is True
    _PROCESS_SCHEMA_REFRESH_LOCK.release()
