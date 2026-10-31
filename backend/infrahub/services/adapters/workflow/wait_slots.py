from __future__ import annotations

import asyncio
import contextlib
import weakref
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient


class PrefectClientWaitSlots:
    """Bound how many workflow runs are awaited at the same time through one Prefect client."""

    def __init__(self, capacity: int) -> None:
        self._capacity = capacity
        # A client lives as long as the flow run that shares it, so its slots go away with it.
        self._slots: weakref.WeakKeyDictionary[PrefectClient, asyncio.Semaphore] = weakref.WeakKeyDictionary()

    def slot(self, client: PrefectClient | None) -> contextlib.AbstractAsyncContextManager[None]:
        """Return the slot to hold while awaiting a run through `client`, or no bound without a shared client."""
        if client is None:
            return contextlib.nullcontext()
        if client not in self._slots:
            self._slots[client] = asyncio.Semaphore(self._capacity)
        return self._slots[client]
