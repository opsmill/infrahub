from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from tests.helpers.constants import LOCK_WAIT_TIMEOUT_SECONDS

if TYPE_CHECKING:
    from tests.adapters.lock import LockTimeline


async def wait_until_waiting(timeline: LockTimeline, name: str) -> None:
    """Return once exactly one caller waits for the lock `name`.

    Raises:
        TimeoutError: When no caller waits for the lock within the lock wait limit of the tests.

    """

    async def _poll() -> None:
        while timeline.waiting(name) != 1:  # noqa: ASYNC110
            await asyncio.sleep(0.01)

    await asyncio.wait_for(_poll(), timeout=LOCK_WAIT_TIMEOUT_SECONDS)
