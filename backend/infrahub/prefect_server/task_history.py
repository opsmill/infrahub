from __future__ import annotations

import asyncio
import itertools
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Protocol, assert_never
from uuid import uuid4

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, status
from prefect.logging import get_logger
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.database.configurations import AsyncPostgresConfiguration
from prefect.server.schemas.states import TERMINAL_STATES
from prefect.server.utilities.database import get_max_query_parameters
from prefect.settings import get_current_settings
from sqlalchemy.dialects.postgresql import REGCLASS
from sqlalchemy.exc import DBAPIError

from .task_history_models import CleanupJob, CleanupJobState, CleanupRequest, CleanupRewrite, TaskHistorySize

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.ext.asyncio import AsyncConnection

log = get_logger(__name__)

_TASK_HISTORY_TABLES = ("flow_run", "flow_run_state", "task_run", "task_run_state", "log", "artifact")
_ACTIVITY_LOG_TABLES = ("events", "event_resources")
# Above this many pages a table's live size is estimated from a sample of its pages, so a mostly live table is not read whole.
_EXACT_MEASURE_PAGES = 10_000
# Counting stops here, so the count of old runs stays fast on a task history of millions of runs.
_OLD_RUNS_COUNT_LIMIT = 100_000
# Short, because every query that reaches a table while a rewrite waits for it queues behind the rewrite.
_REWRITE_LOCK_TIMEOUT = timedelta(seconds=3)
_REWRITE_RETRIES = 4
_REWRITE_RETRY_PAUSE = timedelta(seconds=20)
# A stopped rewrite leaves its table as it was, so the limit only bounds how long the table stays locked.
_REWRITE_TIME_LIMIT = timedelta(seconds=60)
# Lets Prefect catch up on the writes that waited for one table before the next one is locked, so it grows with the wait.
_REWRITE_PAUSE_FACTOR = 10
_REWRITE_MAX_PAUSE = timedelta(seconds=60)
_SQLSTATE_LOCK_NOT_AVAILABLE = "55P03"
_SQLSTATE_QUERY_CANCELED = "57014"
_CLEANUP_LOCK_KEY = int.from_bytes(b"taskhist", byteorder="big")
# Outlasts a day of deletes; Prefect 3.8.6 turns None into the API's 10 s timeout, and so into the API's engine.
_MAINTENANCE_STATEMENT_TIMEOUT = timedelta(hours=24)
# The tuple header and line pointer that Postgres stores with each row, which the size of its values leaves out.
_ROW_OVERHEAD_BYTES = 28
_PG_CLASS = sa.table("pg_class", sa.column("oid"), sa.column("reltoastrelid"))


class CleanupLock(Protocol):
    """Lets one cleanup run at a time across every task manager on the database."""

    async def try_acquire(self) -> bool: ...

    async def release(self) -> None: ...


class ProcessCleanupLock:
    """Cleanup lock of this process, for SQLite, which only one task manager process serves."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    async def try_acquire(self) -> bool:
        return self._lock.acquire(blocking=False)

    async def release(self) -> None:
        self._lock.release()


class PostgresAdvisoryLock:
    """Cleanup lock held as a Postgres advisory lock by a connection of its own until it is released."""

    def __init__(self, db: PrefectDBInterface, key: int) -> None:
        self._db = db
        self._key = key
        self._connection: AsyncConnection | None = None

    async def try_acquire(self) -> bool:
        engine = await self._db.engine()
        connection = await engine.connect()
        acquired = False
        try:
            # Autocommit, so the session holding the lock never sits idle in a transaction for the whole cleanup.
            await connection.execution_options(isolation_level="AUTOCOMMIT")
            acquired = bool(await connection.scalar(sa.select(sa.func.pg_try_advisory_lock(self._key))))
        finally:
            if not acquired:
                await connection.close()
        if acquired:
            self._connection = connection
        return acquired

    async def release(self) -> None:
        if self._connection is None:
            return
        connection, self._connection = self._connection, None
        # Ending the session releases the lock, and a discarded connection cannot return to the pool still holding it.
        await connection.invalidate()
        await connection.close()


class TaskHistoryTables:
    """Deletes finished top-level runs on the same conditions as Prefect's own cleanup of old runs."""

    def __init__(self, db: PrefectDBInterface, ids_per_statement: int) -> None:
        self._db = db
        self._ids_per_statement = ids_per_statement

    def _eligible(self, ended_before: datetime, ended_from: datetime | None) -> sa.ColumnElement[bool]:
        conditions = [
            self._db.FlowRun.parent_task_run_id.is_(None),
            self._db.FlowRun.state_type.in_(TERMINAL_STATES),
            self._db.FlowRun.end_time.is_not(None),
            self._db.FlowRun.end_time < ended_before,
        ]
        if ended_from is not None:
            conditions.append(self._db.FlowRun.end_time >= ended_from)
        return sa.and_(*conditions)

    async def oldest_end_time(self, ended_before: datetime, ended_from: datetime | None = None) -> datetime | None:
        """Return the oldest end time of the runs that may be deleted within the time range."""
        async with self._db.session_context() as session:
            oldest: datetime | None = await session.scalar(
                sa.select(sa.func.min(self._db.FlowRun.end_time)).where(
                    self._eligible(ended_before=ended_before, ended_from=ended_from)
                )
            )
        return oldest

    async def count_runs(self, ended_before: datetime, limit: int) -> int:
        """Return how many runs that ended before the time may be deleted, counting no further than the limit."""
        eligible = sa.select(self._db.FlowRun.id).where(self._eligible(ended_before=ended_before, ended_from=None))
        async with self._db.session_context() as session:
            counted: int = await session.scalar(
                sa.select(sa.func.count()).select_from(eligible.limit(limit).subquery())
            )
        return counted

    async def delete_runs(self, ended_from: datetime, ended_before: datetime) -> int:
        """Delete the runs that ended within the time range, then their logs and artifacts, in one transaction.

        Task runs and states go with their runs by cascade, and runs that another session holds locked are skipped.
        """
        db = self._db
        async with db.session_context(begin_transaction=True, with_for_update=True) as session:
            eligible = (
                sa.select(db.FlowRun.id)
                .where(self._eligible(ended_before=ended_before, ended_from=ended_from))
                .with_for_update(skip_locked=True)
            )
            deleted = (
                await session.scalars(sa.delete(db.FlowRun).where(db.FlowRun.id.in_(eligible)).returning(db.FlowRun.id))
            ).all()
            for flow_run_ids in itertools.batched(deleted, self._ids_per_statement):
                await session.execute(sa.delete(db.Log).where(db.Log.flow_run_id.in_(flow_run_ids)))
                await session.execute(sa.delete(db.Artifact).where(db.Artifact.flow_run_id.in_(flow_run_ids)))
        return len(deleted)


@dataclass(frozen=True)
class TableSpace:
    """The bytes a table takes on disk, and the bytes its live rows hold of them."""

    disk_bytes: int
    live_bytes: int


class TableOutcome(StrEnum):
    """What the rewrite of one table did."""

    REWRITTEN = "rewritten"
    LOCKED = "locked"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True)
class _TableRewrite:
    outcome: TableOutcome
    held_for: timedelta


class TableRewriter(Protocol):
    """Rewrites tables to return the space of deleted rows to the disk."""

    @property
    def tables(self) -> tuple[str, ...]:
        """The tables it may rewrite, in the order it rewrites them."""
        ...

    async def total_size(self) -> int: ...

    async def space(self, table: str) -> TableSpace:
        """Measure the disk space of the table, and the part of it that its live rows hold."""
        ...

    async def rewrite(self, tables: list[str], on_table: Callable[[str, TableOutcome], None]) -> None:
        """Rewrite the tables one by one, reporting each table's outcome as soon as it is known."""
        ...


async def total_size(db: PrefectDBInterface, tables: tuple[str, ...]) -> int:
    """Return the disk space in bytes of the tables with their indexes."""
    async with db.session_context() as session:
        sizes = (
            await session.execute(
                sa.select(*(sa.func.pg_total_relation_size(sa.cast(sa.literal(table), REGCLASS)) for table in tables))
            )
        ).one()
    return sum(sizes)


class PostgresTableRewriter:
    """Rewrites tables with VACUUM FULL, giving up on a table that stays locked or takes too long."""

    def __init__(
        self,
        db: PrefectDBInterface,
        tables: tuple[str, ...],
        exact_measure_pages: int,
        lock_timeout: timedelta,
        retries: int,
        retry_pause: timedelta,
        time_limit: timedelta,
        pause_factor: int,
        max_pause: timedelta,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._db = db
        self._tables = tables
        self._exact_measure_pages = exact_measure_pages
        self._lock_timeout = lock_timeout
        self._retries = retries
        self._retry_pause = retry_pause
        self._time_limit = time_limit
        self._pause_factor = pause_factor
        self._max_pause = max_pause
        self._clock = clock

    @property
    def tables(self) -> tuple[str, ...]:
        return self._tables

    async def total_size(self) -> int:
        return await total_size(db=self._db, tables=self._tables)

    async def space(self, table: str) -> TableSpace:
        relation = sa.cast(sa.literal(table), REGCLASS)
        toast_relation = sa.select(_PG_CLASS.c.reltoastrelid).where(_PG_CLASS.c.oid == relation).scalar_subquery()
        disk_bytes = sa.func.pg_relation_size(relation) + sa.case(
            (toast_relation == 0, 0), else_=sa.func.pg_relation_size(toast_relation)
        )
        main_bytes = sa.func.pg_relation_size(relation)
        block_size = sa.cast(sa.func.current_setting("block_size"), sa.BigInteger)
        async with self._db.session_context() as session:
            disk, main, block = (await session.execute(sa.select(disk_bytes, main_bytes, block_size))).one()
            main_pages = main // block
            percent = (
                100.0 if main_pages <= self._exact_measure_pages else 100.0 * self._exact_measure_pages / main_pages
            )
            live = await session.scalar(self._live_bytes(table=table, percent=percent))
        return TableSpace(disk_bytes=disk, live_bytes=round(live * 100.0 / percent))

    def _live_bytes(self, table: str, percent: float) -> sa.Select[tuple[int]]:
        """Select the bytes that the live rows hold in the given percent of the table's pages, picked at random."""
        whole = self._db.Base.metadata.tables[table]
        source = whole if percent >= 100.0 else sa.tablesample(whole, sa.func.system(percent), name="sampled")
        # Column by column, because the size of a whole row reads every value stored out of line.
        row_bytes: sa.ColumnElement[int] = sa.literal(_ROW_OVERHEAD_BYTES)
        for column in source.columns:
            row_bytes += sa.func.coalesce(sa.func.pg_column_size(column), 0)
        return sa.select(sa.func.coalesce(sa.func.sum(row_bytes), 0)).select_from(source)

    async def rewrite(self, tables: list[str], on_table: Callable[[str, TableOutcome], None]) -> None:
        engine = await self._db.engine()
        async with engine.connect() as connection:
            try:
                await connection.execution_options(isolation_level="AUTOCOMMIT")
                await _set_timeout(connection=connection, name="lock_timeout", value=self._lock_timeout)
                held_for = timedelta(0)
                for table in tables:
                    await asyncio.sleep(min(held_for * self._pause_factor, self._max_pause).total_seconds())
                    rewrite = await self._rewrite_table(connection=connection, table=table)
                    held_for = rewrite.held_for
                    on_table(table, rewrite.outcome)
            finally:
                # Discarded, so no pooled connection keeps the timeouts of this session.
                await connection.invalidate()

    async def _rewrite_table(self, connection: AsyncConnection, table: str) -> _TableRewrite:
        quoted = connection.dialect.identifier_preparer.quote(table)
        attempts = 1 + self._retries
        for attempt in range(1, attempts + 1):
            if attempt > 1:
                await asyncio.sleep(self._retry_pause.total_seconds())
            await _set_timeout(connection=connection, name="statement_timeout", value=self._time_limit)
            started = self._clock()
            try:
                await connection.execute(sa.text(f"VACUUM FULL {quoted}"))
            except DBAPIError as exc:
                outcome = rewrite_error_outcome(error=exc)
                if outcome is TableOutcome.LOCKED:
                    log.warning(f"Task history cleanup: {table} stayed locked, rewrite attempt {attempt} of {attempts}")
                    continue
                if outcome is TableOutcome.TIMED_OUT:
                    log.warning(f"Task history cleanup: stopped the rewrite of {table}, which took too long")
                    return _TableRewrite(outcome=outcome, held_for=self._since(started))
                raise
            held_for = self._since(started)
            log.info(f"Task history cleanup: rewrote {table} in {held_for.total_seconds():.1f} s")
            await self._refresh_statistics(connection=connection, table=table)
            return _TableRewrite(outcome=TableOutcome.REWRITTEN, held_for=held_for)
        return _TableRewrite(outcome=TableOutcome.LOCKED, held_for=timedelta(0))

    def _since(self, started: float) -> timedelta:
        return timedelta(seconds=self._clock() - started)

    async def _refresh_statistics(self, connection: AsyncConnection, table: str) -> None:
        """Refresh the planner statistics of a rewritten table, which its rewrite does not update."""
        try:
            await _set_timeout(connection=connection, name="statement_timeout", value=timedelta(0))
            await connection.execute(sa.text(f"VACUUM (ANALYZE) {connection.dialect.identifier_preparer.quote(table)}"))
        # The table is already rewritten, and autovacuum refreshes the statistics later anyway.
        except DBAPIError as exc:
            log.warning(f"Task history cleanup: could not refresh the statistics of {table}: {exc}")


async def _set_timeout(connection: AsyncConnection, name: str, value: timedelta) -> None:
    milliseconds = int(value / timedelta(milliseconds=1))
    await connection.execute(sa.select(sa.func.set_config(name, f"{milliseconds}ms", False)))


def rewrite_error_outcome(error: DBAPIError) -> TableOutcome | None:
    """Return what a rewrite stopped by the error did with its table, or None when the error must fail the cleanup.

    A table that stayed locked may still be tried again.
    """
    sqlstate = _sqlstate(error=error)
    if sqlstate == _SQLSTATE_QUERY_CANCELED:
        return TableOutcome.TIMED_OUT
    if sqlstate == _SQLSTATE_LOCK_NOT_AVAILABLE:
        return TableOutcome.LOCKED
    return None


def _sqlstate(error: DBAPIError) -> str | None:
    # SQLAlchemy 2.0 sets sqlstate on its asyncpg dialect's error without declaring the attribute.
    sqlstate = getattr(error.orig, "sqlstate", None)
    return sqlstate if isinstance(sqlstate, str) else None


def _record_outcome(job: CleanupJob, table: str, outcome: TableOutcome) -> None:
    match outcome:
        case TableOutcome.REWRITTEN:
            job.rewritten.append(table)
        case TableOutcome.LOCKED:
            job.not_rewritten.append(table)
        case TableOutcome.TIMED_OUT:
            job.timed_out.append(table)
        case _:
            assert_never(outcome)


def _start_of_day(moment: datetime) -> datetime:
    return moment.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


class TaskHistoryCleanup:
    """Deletes the task history older than a cleanup's cutoff a day at a time, then rewrites the tables as it asks."""

    def __init__(self, tables: TaskHistoryTables, rewriter: TableRewriter | None) -> None:
        self._tables = tables
        self._rewriter = rewriter

    async def delete(self, job: CleanupJob) -> None:
        """Delete the runs that ended before the job's cutoff, recording the progress on the job."""
        log.info(f"Task history cleanup {job.id}: deleting the runs that ended before {job.cutoff.isoformat()}")
        if self._rewriter is not None:
            job.size_before = await self._rewriter.total_size()
        await self._delete_old_runs(job=job)

    async def rewrite(self, job: CleanupJob, mode: CleanupRewrite) -> None:
        """Rewrite the tables the mode asks for against their free space now, recording each table's outcome on the job."""
        if self._rewriter is None:
            return
        if mode is CleanupRewrite.IF_FREED:
            freed = await self._freed_tables(job=job, rewriter=self._rewriter)
            if freed:
                await self._rewriter.rewrite(
                    tables=freed,
                    on_table=lambda table, outcome: _record_outcome(job=job, table=table, outcome=outcome),
                )
        job.size_after = await self._rewriter.total_size()

    async def _freed_tables(self, job: CleanupJob, rewriter: TableRewriter) -> list[str]:
        """Return the tables whose live rows hold less than half of their disk space, recording the others on the job."""
        freed: list[str] = []
        mostly_live: list[str] = []
        for table in rewriter.tables:
            space = await rewriter.space(table=table)
            if space.live_bytes * 2 < space.disk_bytes:
                freed.append(table)
                continue
            mostly_live.append(table)
            log.info(
                f"Task history cleanup {job.id}: left {table} as it is, "
                f"its live rows hold {space.live_bytes} of its {space.disk_bytes} bytes"
            )
        job.mostly_live = mostly_live
        return freed

    async def _delete_old_runs(self, job: CleanupJob) -> None:
        # A deleted parent leaves its subflows top-level, and they may have ended on a day already passed.
        while await self._delete_pass(job=job):
            pass
        log.info(f"Task history cleanup {job.id}: deleted {job.deleted_runs} runs")

    async def _delete_pass(self, job: CleanupJob) -> int:
        """Delete the runs day by day from the oldest, returning how many this pass deleted."""
        deleted_in_pass = 0
        oldest = await self._tables.oldest_end_time(ended_before=job.cutoff)
        while oldest is not None:
            day_start = _start_of_day(oldest)
            day_end = min(day_start + timedelta(days=1), job.cutoff)
            job.current_day = day_start.date()
            deleted = await self._tables.delete_runs(ended_from=day_start, ended_before=day_end)
            job.deleted_runs += deleted
            deleted_in_pass += deleted
            log.info(f"Task history cleanup {job.id}: deleted {deleted} runs that ended on {job.current_day}")
            oldest = await self._tables.oldest_end_time(ended_before=job.cutoff, ended_from=day_end)
        return deleted_in_pass


class CleanupJobs:
    """The cleanups this task manager process ran, of which at most one runs at a time."""

    def __init__(self) -> None:
        self._jobs: dict[str, CleanupJob] = {}
        self._running: CleanupJob | None = None
        self._tasks: set[asyncio.Task[None]] = set()
        self._starting = asyncio.Lock()

    def get(self, job_id: str) -> CleanupJob | None:
        return self._jobs.get(job_id)

    async def start(self, job: CleanupJob, lock: CleanupLock, cleanup: TaskHistoryCleanup) -> CleanupJob | None:
        """Start the job in the background, unless a job already runs in this process or the lock is held elsewhere.

        A job already running takes the job's rewrite mode when that one is stronger.

        Returns:
            The job running in this process, or None when another task manager holds the lock.

        """
        async with self._starting:
            if self._running is not None:
                if job.rewrite.strength > self._running.rewrite.strength:
                    self._running.rewrite = job.rewrite
                return self._running
            if not await lock.try_acquire():
                return None
            self._jobs[job.id] = job
            self._running = job
        task = asyncio.create_task(self._run(job=job, lock=lock, cleanup=cleanup))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return job

    async def _run(self, job: CleanupJob, lock: CleanupLock, cleanup: TaskHistoryCleanup) -> None:
        """Run the job to its end, deciding the rewrite again whenever a start raised its mode after the decision."""
        try:
            await cleanup.delete(job=job)
            decided: CleanupRewrite | None = None
            while True:
                # Ending the job in the same hold as the check leaves no moment where a start raises a mode it ignores.
                async with self._starting:
                    if job.rewrite is decided:
                        self._running = None
                        await lock.release()
                        job.state = CleanupJobState.COMPLETED
                        return
                    decided = job.rewrite
                await cleanup.rewrite(job=job, mode=decided)
        # A background job has no caller to raise to, so the failure is logged and recorded on the job instead.
        except Exception as exc:
            log.exception(f"Task history cleanup {job.id} failed")
            job.state = CleanupJobState.FAILED
            job.error = f"The cleanup failed with {type(exc).__name__}; the task manager log has the details"
        finally:
            async with self._starting:
                if self._running is job:
                    self._running = None
                    await lock.release()


class _MaintenancePostgresConfiguration(AsyncPostgresConfiguration):
    """Prefect's Postgres configuration on a small pool of its own, whose statements may run for minutes."""

    def __init__(self, connection_url: str) -> None:
        super().__init__(
            connection_url=connection_url,
            timeout=_MAINTENANCE_STATEMENT_TIMEOUT.total_seconds(),
            sqlalchemy_pool_size=2,
            sqlalchemy_max_overflow=1,
        )


def _maintenance_database(db: PrefectDBInterface) -> PrefectDBInterface:
    maintenance = PrefectDBInterface(
        database_config=_MaintenancePostgresConfiguration(connection_url=db.database_config.connection_url),
        query_components=db.queries,
        orm=db.orm,
    )
    if not isinstance(maintenance, PrefectDBInterface):
        raise TypeError(f"Prefect built a {type(maintenance).__name__} instead of a database interface")
    return maintenance


_CLEANUP_JOBS = CleanupJobs()
_PROCESS_CLEANUP_LOCK = ProcessCleanupLock()


def get_cleanup_jobs() -> CleanupJobs:
    return _CLEANUP_JOBS


def get_cleanup_lock(db: Annotated[PrefectDBInterface, Depends(provide_database_interface)]) -> CleanupLock:
    if isinstance(db.database_config, AsyncPostgresConfiguration):
        return PostgresAdvisoryLock(db=_maintenance_database(db), key=_CLEANUP_LOCK_KEY)
    return _PROCESS_CLEANUP_LOCK


def build_task_history_cleanup(
    db: Annotated[PrefectDBInterface, Depends(provide_database_interface)],
) -> TaskHistoryCleanup:
    ids_per_statement = get_max_query_parameters()
    if isinstance(db.database_config, AsyncPostgresConfiguration):
        maintenance = _maintenance_database(db)
        return TaskHistoryCleanup(
            tables=TaskHistoryTables(db=maintenance, ids_per_statement=ids_per_statement),
            rewriter=PostgresTableRewriter(
                db=maintenance,
                tables=_TASK_HISTORY_TABLES + _ACTIVITY_LOG_TABLES,
                exact_measure_pages=_EXACT_MEASURE_PAGES,
                lock_timeout=_REWRITE_LOCK_TIMEOUT,
                retries=_REWRITE_RETRIES,
                retry_pause=_REWRITE_RETRY_PAUSE,
                time_limit=_REWRITE_TIME_LIMIT,
                pause_factor=_REWRITE_PAUSE_FACTOR,
                max_pause=_REWRITE_MAX_PAUSE,
            ),
        )
    return TaskHistoryCleanup(tables=TaskHistoryTables(db=db, ids_per_statement=ids_per_statement), rewriter=None)


router = APIRouter(prefix="/task-history", tags=["Infrahub"])


@router.post("/cleanup", status_code=status.HTTP_202_ACCEPTED)
async def start_cleanup(
    body: CleanupRequest,
    jobs: Annotated[CleanupJobs, Depends(get_cleanup_jobs)],
    lock: Annotated[CleanupLock, Depends(get_cleanup_lock)],
    cleanup: Annotated[TaskHistoryCleanup, Depends(build_task_history_cleanup)],
) -> CleanupJob:
    """Start deleting the task history older than the task manager's retention, or return the cleanup already running.

    A cleanup already running takes the rewrite asked for when that one is stronger than its own.

    Raises:
        HTTPException: 409 when another task manager runs a cleanup.

    """
    retention = get_current_settings().server.services.db_vacuum.retention_period
    job = CleanupJob(
        id=uuid4().hex,
        state=CleanupJobState.RUNNING,
        rewrite=body.rewrite,
        cutoff=datetime.now(UTC) - retention,
    )
    started = await jobs.start(job=job, lock=lock, cleanup=cleanup)
    if started is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="a cleanup is running elsewhere")
    return started


@router.get("/size")
async def read_task_history_size(
    db: Annotated[PrefectDBInterface, Depends(provide_database_interface)],
) -> TaskHistorySize:
    """Return the disk space of the task history tables, which is not measured on SQLite, and how many runs are old."""
    retention = get_current_settings().server.services.db_vacuum.retention_period
    tables = TaskHistoryTables(db=db, ids_per_statement=get_max_query_parameters())
    counted = await tables.count_runs(ended_before=datetime.now(UTC) - retention, limit=_OLD_RUNS_COUNT_LIMIT + 1)
    size = None
    if isinstance(db.database_config, AsyncPostgresConfiguration):
        size = await total_size(db=db, tables=_TASK_HISTORY_TABLES)
    return TaskHistorySize(
        size=size,
        old_runs=min(counted, _OLD_RUNS_COUNT_LIMIT),
        old_runs_limit_reached=counted > _OLD_RUNS_COUNT_LIMIT,
    )


@router.get("/cleanup/{job_id}")
async def read_cleanup(job_id: str, jobs: Annotated[CleanupJobs, Depends(get_cleanup_jobs)]) -> CleanupJob:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="the cleanup is unknown to this task manager")
    return job
