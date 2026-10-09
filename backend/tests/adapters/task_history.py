from __future__ import annotations

import asyncio

from infrahub.prefect_server.task_history import TableSpace

PAUSE_TIMEOUT_SECONDS = 30


class RecordingRewriter:
    """Records its calls in order, measuring 1000 bytes until a rewrite and 100 after it, and the given runs table.

    Given a call number, it pauses at that call until the test lets it go on.
    """

    def __init__(self, flow_run_space: TableSpace, pause_at_call: int | None = None) -> None:
        self.calls: list[str] = []
        self._flow_run_space = flow_run_space
        self._pause_at_call = pause_at_call
        self._paused = asyncio.Event()
        self._resumed = asyncio.Event()

    async def total_size(self) -> int:
        await self._record(call="total_size")
        return 1000 if "rewrite" not in self.calls else 100

    async def flow_run_space(self) -> TableSpace:
        await self._record(call="flow_run_space")
        return self._flow_run_space

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


class FailingRewriter:
    """Measures 1000 bytes and a runs table with no live rows, and raises on every rewrite.

    It proves that a failed cleanup lets the next one start.
    """

    async def total_size(self) -> int:
        return 1000

    async def flow_run_space(self) -> TableSpace:
        return TableSpace(disk_bytes=1000, live_bytes=0)

    async def rewrite(self) -> list[str]:
        raise RuntimeError("rewrite rejected")
