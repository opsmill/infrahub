from __future__ import annotations

import asyncio

PAUSE_TIMEOUT_SECONDS = 30


class RecordingRewriter:
    """Records its calls in order, measuring 1000 bytes until a rewrite and 100 after it.

    Given a call number, it pauses at that call until the test lets it go on.
    """

    def __init__(self, pause_at_call: int | None = None) -> None:
        self.calls: list[str] = []
        self._pause_at_call = pause_at_call
        self._paused = asyncio.Event()
        self._resumed = asyncio.Event()

    async def total_size(self) -> int:
        await self._record(call="total_size")
        return 1000 if "rewrite" not in self.calls else 100

    async def rewrite(self) -> list[str]:
        await self._record(call="rewrite")
        return ["log"]

    async def wait_until_paused(self) -> None:
        async with asyncio.timeout(PAUSE_TIMEOUT_SECONDS):
            await self._paused.wait()

    def resume(self) -> None:
        self._resumed.set()

    async def _record(self, call: str) -> None:
        self.calls.append(call)
        if len(self.calls) == self._pause_at_call:
            self._paused.set()
            async with asyncio.timeout(PAUSE_TIMEOUT_SECONDS):
                await self._resumed.wait()
