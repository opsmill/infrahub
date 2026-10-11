from __future__ import annotations

import asyncio

from infrahub.prefect_server.task_history import TableSpace

PAUSE_TIMEOUT_SECONDS = 30


class RecordingRewriter:
    """Records its calls in order, measuring 1000 bytes until a rewrite and 100 after it, and the given space of each table.

    Its rewrite leaves out the tables given as locked. Given a call number, it pauses at that call until the test lets it go on.
    """

    def __init__(
        self, spaces: dict[str, TableSpace], locked: tuple[str, ...] = (), pause_at_call: int | None = None
    ) -> None:
        self.calls: list[str] = []
        self._spaces = spaces
        self._locked = locked
        self._pause_at_call = pause_at_call
        self._paused = asyncio.Event()
        self._resumed = asyncio.Event()

    @property
    def tables(self) -> tuple[str, ...]:
        return tuple(self._spaces)

    async def total_size(self) -> int:
        await self._record(call="total_size")
        return 100 if any(call.startswith("rewrite") for call in self.calls) else 1000

    async def space(self, table: str) -> TableSpace:
        await self._record(call=f"space {table}")
        return self._spaces[table]

    async def rewrite(self, tables: list[str]) -> list[str]:
        await self._record(call=f"rewrite {' '.join(tables)}")
        return [table for table in tables if table in self._locked]

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

    @property
    def tables(self) -> tuple[str, ...]:
        return ("flow_run",)

    async def total_size(self) -> int:
        return 1000

    async def space(self, table: str) -> TableSpace:
        return TableSpace(disk_bytes=1000, live_bytes=0)

    async def rewrite(self, tables: list[str]) -> list[str]:
        raise RuntimeError("rewrite rejected")
