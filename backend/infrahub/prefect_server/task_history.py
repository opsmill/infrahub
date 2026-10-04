from __future__ import annotations

import asyncio
import itertools
import threading
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Protocol, assert_never
from uuid import uuid4

import sqlalchemy as sa
from asyncpg.exceptions import LockNotAvailableError
from fastapi import APIRouter, Depends, HTTPException, status
from prefect.logging import get_logger
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.database.configurations import AsyncPostgresConfiguration
from prefect.server.schemas.states import TERMINAL_STATES
from prefect.server.utilities.database import get_max_query_parameters
from prefect.settings import get_current_settings
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.dialects.postgresql import REGCLASS
from sqlalchemy.exc import DBAPIError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection

log = get_logger(__name__)

_TASK_HISTORY_TABLES = ("flow_run", "flow_run_state", "task_run", "task_run_state", "log", "artifact")
_REWRITE_LOCK_TIMEOUT = timedelta(seconds=60)
_REWRITE_RETRIES = 3
_CLEANUP_LOCK_KEY = int.from_bytes(b"taskhist", byteorder="big")
# Outlasts a day of deletes; None would share the one-connection engine of Prefect 3.8.6's own vacuum.
_MAINTENANCE_STATEMENT_TIMEOUT = timedelta(hours=24)


class CleanupJobState(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class CleanupRewrite(StrEnum):
    """When a cleanup rewrites the task history tables after its deletes; nothing is rewritten on SQLite."""

    NEVER = "never"
    IF_FREED = "if_freed"
    """When the deletes, including the task manager's own meanwhile, freed more than half of the runs."""
    ALWAYS = "always"

    @property
    def strength(self) -> int:
        """Rank of the mode, which rewrites the tables whenever a mode of a lower rank would."""
        match self:
            case CleanupRewrite.NEVER:
                strength = 0
            case CleanupRewrite.IF_FREED:
                strength = 1
            case CleanupRewrite.ALWAYS:
                strength = 2
            case _:
                assert_never(self)
        return strength


class CleanupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rewrite: CleanupRewrite = Field(
        default=CleanupRewrite.NEVER, description="When to rewrite the task history tables after the deletes"
    )


class CleanupJob(BaseModel):
    id: str
    state: CleanupJobState
    rewrite: CleanupRewrite = Field(
        description="When to rewrite the tables after the deletes, raised by a request for a stronger mode while it runs"
    )
    rewritten: bool = Field(
        default=False, description="Whether the tables were rewritten, which never happens on SQLite"
    )
    cutoff: datetime = Field(description="Runs that ended before this time are deleted")
    deleted_runs: int = 0
    current_day: date | None = Field(default=None, description="Day of end times being deleted")
    size_before: int | None = Field(
        default=None, description="Total size in bytes of the task history tables before the deletes, on Postgres"
    )
    size_after: int | None = Field(
        default=None, description="Total size in bytes of the task history tables at the end, on Postgres"
    )
    not_rewritten: list[str] = Field(
        default_factory=list, description="Tables whose rewrite still waited too long for a lock after its retries"
    )
    error: str | None = None


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

    async def count_runs(self) -> int:
        async with self._db.session_context() as session:
            count: int = await session.scalar(sa.select(sa.func.count()).select_from(self._db.FlowRun)) or 0
        return count


class TableRewriter(Protocol):
    """Rewrites the task history tables to return the space of deleted rows to the disk."""

    async def total_size(self) -> int: ...

    async def rewrite(self) -> list[str]:
        """Rewrite every table, returning those that stayed locked by other sessions."""
        ...


class PostgresTableRewriter:
    """Rewrites tables with VACUUM FULL, giving up on a table that stays locked."""

    def __init__(self, db: PrefectDBInterface, tables: tuple[str, ...], lock_timeout: timedelta, retries: int) -> None:
        self._db = db
        self._tables = tables
        self._lock_timeout = lock_timeout
        self._retries = retries

    async def total_size(self) -> int:
        async with self._db.session_context() as session:
            sizes = (
                await session.execute(
                    sa.select(
                        *(
                            sa.func.pg_total_relation_size(sa.cast(sa.literal(table), REGCLASS))
                            for table in self._tables
                        )
                    )
                )
            ).one()
        return sum(sizes)

    async def rewrite(self) -> list[str]:
        engine = await self._db.engine()
        not_rewritten: list[str] = []
        async with engine.connect() as connection:
            try:
                await connection.execution_options(isolation_level="AUTOCOMMIT")
                await connection.execute(
                    sa.select(sa.func.set_config("lock_timeout", f"{int(self._lock_timeout.total_seconds())}s", False))
                )
                for table in self._tables:
                    if not await self._rewrite_table(connection=connection, table=table):
                        not_rewritten.append(table)
            finally:
                # Discarded, so no pooled connection keeps the lock timeout of this session.
                await connection.invalidate()
        return not_rewritten

    async def _rewrite_table(self, connection: AsyncConnection, table: str) -> bool:
        statement = sa.text(f"VACUUM FULL {connection.dialect.identifier_preparer.quote(table)}")
        attempts = 1 + self._retries
        for attempt in range(1, attempts + 1):
            try:
                await connection.execute(statement)
            except DBAPIError as exc:
                if not _is_lock_timeout(exc):
                    raise
                log.warning(f"Task history cleanup: {table} stayed locked, rewrite attempt {attempt} of {attempts}")
                continue
            log.info(f"Task history cleanup: rewrote {table}")
            return True
        return False


def _is_lock_timeout(error: DBAPIError) -> bool:
    return isinstance(error.orig, Exception) and isinstance(error.orig.__cause__, LockNotAvailableError)


def _start_of_day(moment: datetime) -> datetime:
    return moment.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


class RewriteSettlement(Protocol):
    """Hands a running cleanup the rewrite mode to decide with, until the mode it decided with is final."""

    async def __call__(self, decided: CleanupRewrite | None) -> CleanupRewrite | None:
        """Return the cleanup's mode unless it is the one decided with, else end the cleanup and return None."""
        ...


class TaskHistoryCleanup:
    """Deletes the task history older than a cleanup's cutoff a day at a time, then rewrites the tables as it asks."""

    def __init__(self, tables: TaskHistoryTables, rewriter: TableRewriter | None) -> None:
        self._tables = tables
        self._rewriter = rewriter

    async def run(self, job: CleanupJob, settle: RewriteSettlement) -> None:
        """Run the cleanup, recording its progress and outcome on the job.

        The rewrite is decided again with each mode the settlement hands back, against the runs counted before the
        deletes, until that mode is final; tables already rewritten are never rewritten again.
        """
        log.info(f"Task history cleanup {job.id}: deleting the runs that ended before {job.cutoff.isoformat()}")
        runs_before = 0
        if self._rewriter is not None:
            job.size_before = await self._rewriter.total_size()
            runs_before = await self._tables.count_runs()
        await self._delete_old_runs(job=job)
        decided: CleanupRewrite | None = None
        while (rewrite := await settle(decided=decided)) is not None:
            await self._decide_rewrite(job=job, rewrite=rewrite, runs_before=runs_before)
            decided = rewrite

    async def _decide_rewrite(self, job: CleanupJob, rewrite: CleanupRewrite, runs_before: int) -> None:
        if self._rewriter is None or job.rewritten:
            return
        if await self._rewrite_wanted(rewrite=rewrite, runs_before=runs_before):
            job.not_rewritten = await self._rewriter.rewrite()
            job.rewritten = True
        job.size_after = await self._rewriter.total_size()

    async def _rewrite_wanted(self, rewrite: CleanupRewrite, runs_before: int) -> bool:
        match rewrite:
            case CleanupRewrite.ALWAYS:
                return True
            case CleanupRewrite.IF_FREED:
                return await self._tables.count_runs() * 2 < runs_before
            case CleanupRewrite.NEVER:
                return False

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
        try:
            await cleanup.run(job=job, settle=self._settlement(job=job, lock=lock))
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

    def _settlement(self, job: CleanupJob, lock: CleanupLock) -> RewriteSettlement:
        async def settle(decided: CleanupRewrite | None) -> CleanupRewrite | None:
            # Ending the job in the same hold as the check leaves no moment where a start raises a mode it ignores.
            async with self._starting:
                if job.rewrite is not decided:
                    return job.rewrite
                self._running = None
                await lock.release()
                job.state = CleanupJobState.COMPLETED
            return None

        return settle


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
                tables=_TASK_HISTORY_TABLES,
                lock_timeout=_REWRITE_LOCK_TIMEOUT,
                retries=_REWRITE_RETRIES,
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


@router.get("/cleanup/{job_id}")
async def read_cleanup(job_id: str, jobs: Annotated[CleanupJobs, Depends(get_cleanup_jobs)]) -> CleanupJob:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="the cleanup is unknown to this task manager")
    return job
