from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from sqlalchemy.exc import DBAPIError

from infrahub.prefect_server.task_history import TableOutcome, TableSpace

if TYPE_CHECKING:
    from collections.abc import Callable

PAUSE_TIMEOUT_SECONDS = 30


class DriverError(Exception):
    """A driver error as SQLAlchemy's asyncpg dialect wraps it, with the SQLSTATE the server sent."""

    def __init__(self, sqlstate: str) -> None:
        super().__init__(f"server error {sqlstate}")
        self.sqlstate = sqlstate


def database_error(sqlstate: str, connection_invalidated: bool = False) -> DBAPIError:
    return DBAPIError(
        statement="VACUUM FULL log",
        params=None,
        orig=DriverError(sqlstate=sqlstate),
        connection_invalidated=connection_invalidated,
    )


class RecordingRewriter:
    """Records its calls in order, measuring 1000 bytes until a rewrite and 100 after it, and the given space of each table.

    Its rewrite reports each table in order: locked, timed out or failed when given as such, rewritten otherwise. Given
    a table to fail on, it raises on reaching that table. Given a call number, it pauses at that call until the test
    lets it go on.
    """

    def __init__(
        self,
        spaces: dict[str, TableSpace],
        locked: tuple[str, ...] = (),
        timed_out: tuple[str, ...] = (),
        failed: tuple[str, ...] = (),
        fails_on: str | None = None,
        pause_at_call: int | None = None,
    ) -> None:
        self.calls: list[str] = []
        self._spaces = spaces
        self._locked = locked
        self._timed_out = timed_out
        self._failed = failed
        self._fails_on = fails_on
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

    async def rewrite(self, tables: list[str], on_table: Callable[[str, TableOutcome], None]) -> None:
        await self._record(call=f"rewrite {' '.join(tables)}")
        for table in tables:
            if table == self._fails_on:
                raise RuntimeError(f"rewrite of {table} rejected")
            if table in self._locked:
                on_table(table, TableOutcome.LOCKED)
            elif table in self._timed_out:
                on_table(table, TableOutcome.TIMED_OUT)
            elif table in self._failed:
                on_table(table, TableOutcome.FAILED)
            else:
                on_table(table, TableOutcome.REWRITTEN)

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
    """Measures 1000 bytes and a runs table with no live rows, and raises on every rewrite before its first table.

    It proves that a failed cleanup lets the next one start.
    """

    @property
    def tables(self) -> tuple[str, ...]:
        return ("flow_run",)

    async def total_size(self) -> int:
        return 1000

    async def space(self, table: str) -> TableSpace:
        return TableSpace(disk_bytes=1000, live_bytes=0)

    async def rewrite(self, tables: list[str], on_table: Callable[[str, TableOutcome], None]) -> None:
        raise RuntimeError("rewrite rejected")


class LosableCleanupLock:
    """A cleanup lock the test can take from its holder, as a database that ends the holding session does."""

    def __init__(self) -> None:
        self._held = False
        self._lost = asyncio.Event()

    async def try_acquire(self) -> bool:
        if self._held:
            return False
        self._held = True
        self._lost = asyncio.Event()
        return True

    async def wait_lost(self) -> None:
        await self._lost.wait()

    async def release(self) -> None:
        self._held = False

    def lose(self) -> None:
        self._lost.set()
