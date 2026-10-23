from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from infrahub.log import get_logger

from .metrics import CONNECTION_POOL_SIZE

if TYPE_CHECKING:
    from collections.abc import Callable

    from neo4j import AsyncDriver

log = get_logger()


def instrument_connection_pool(
    driver: AsyncDriver,
    pool_size: int,
    *,
    record_wait: Callable[[float], None],
    clock: Callable[[], float] = time.monotonic,
) -> None:
    """Export the size of the driver's pool and record how long each connection acquisition waits.

    The neo4j driver (6.x) has no public hook for the acquisition wait, so the private pool's `acquire`
    method is wrapped. A failure to record the wait is logged and never fails the acquisition.
    """
    pool = driver._pool
    CONNECTION_POOL_SIZE.labels(pool.address).set(pool_size)
    acquire = pool.acquire

    async def acquire_and_record_wait(*args: Any, **kwargs: Any) -> Any:
        started = clock()
        try:
            return await acquire(*args, **kwargs)
        finally:
            try:
                record_wait(clock() - started)
            # A broken metric must never fail the query that needed the connection.
            except Exception:
                log.exception("Failed to record the database connection wait")

    pool.acquire = acquire_and_record_wait
