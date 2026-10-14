"""Record which runs work on a repository, and the last run of each operation, in the cache."""

from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from infrahub.git.state.cache_keys import activity_last_run_key, activity_run_key
from infrahub.log import get_logger

from .models import (
    ActivityBranchRecord,
    ActivityRunRecord,
    LastRunRecord,
    RepositoryActivityBranchOutcome,
    RepositoryActivityOperation,
    RepositoryActivityPhase,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable
    from datetime import datetime

    from infrahub.services.adapters.cache import InfrahubCache

log = get_logger()


class ActiveRunNotFoundError(LookupError):
    """Raised when a run id names no run that this process is tracking."""


class ActivityRun:
    """One run on one repository: the handle a flow reports its phase and branch outcomes through.

    Every cache call is best effort, so a cache that cannot be reached never fails the run.
    """

    def __init__(
        self, cache: InfrahubCache, record: ActivityRunRecord, now: Callable[[], datetime], ttl_seconds: int
    ) -> None:
        self._cache = cache
        self._record = record
        self._now = now
        self._ttl_seconds = ttl_seconds
        self._branches: dict[str, RepositoryActivityBranchOutcome] = {}
        self._keep_last_run = False
        # Serializes the renewal and the phase changes, so an older state never reaches the cache after a newer one.
        self._write_lock = asyncio.Lock()

    @property
    def run_id(self) -> str:
        return self._record.run_id

    @property
    def repository_id(self) -> str:
        return self._record.repository_id

    @property
    def operation(self) -> RepositoryActivityOperation:
        return self._record.operation

    async def set_phase(self, phase: RepositoryActivityPhase | None, branch_name: str | None = None) -> None:
        """Record the step the run is in, and the branch it works on, which is None while fetching."""
        async with self._write_lock:
            self._record = self._record.model_copy(
                update={"phase": phase, "branch_name": branch_name, "updated_at": self._now()}
            )
            await self._write_record()

    def record_branch(self, branch_name: str, outcome: RepositoryActivityBranchOutcome) -> None:
        """Record the result of the run for one branch, replacing an earlier result for the same branch."""
        self._branches[branch_name] = outcome

    def keep_last_run(self) -> None:
        """Leave the earlier last run of this operation in place, for a run whose work another run records."""
        self._keep_last_run = True

    async def renew(self) -> None:
        async with self._write_lock:
            self._record = self._record.model_copy(update={"updated_at": self._now()})
            await self._write_record()

    async def finish(self, last_run_ttl_seconds: int) -> None:
        """Write the last run of this operation, unless the run keeps the previous one, then delete the run record."""
        async with self._write_lock:
            if not self._keep_last_run:
                await self._write_last_run(last_run_ttl_seconds=last_run_ttl_seconds)
            try:
                await self._cache.delete(key=self._run_key)
            # Best effort: the record expires on its own when it cannot be deleted.
            except Exception as exc:  # noqa: BLE001
                log.warning("Could not delete the run record", repository_id=self.repository_id, error=str(exc))

    async def _write_last_run(self, last_run_ttl_seconds: int) -> None:
        last_run = LastRunRecord(
            operation=self._record.operation,
            started_at=self._record.started_at,
            finished_at=self._now(),
            branches=[
                ActivityBranchRecord(branch_name=branch_name, outcome=outcome)
                for branch_name, outcome in self._branches.items()
            ],
        )
        key = activity_last_run_key(repository_id=self.repository_id, operation=self.operation.value)
        try:
            await self._cache.set(key=key, value=last_run.model_dump_json(), expires=last_run_ttl_seconds)
        # Best effort: a lost activity record must never fail the run it describes.
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not record the last run", repository_id=self.repository_id, error=str(exc))

    @property
    def _run_key(self) -> str:
        return activity_run_key(repository_id=self.repository_id, run_id=self.run_id)

    async def _write_record(self) -> None:
        try:
            await self._cache.set(key=self._run_key, value=self._record.model_dump_json(), expires=self._ttl_seconds)
        # Best effort: a lost activity record must never fail the run it describes.
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not write the run record", repository_id=self.repository_id, error=str(exc))


class ActiveRuns:
    """The runs this process is tracking, so an in-process subflow reaches the same run as the flow that started it."""

    def __init__(self) -> None:
        self._runs: dict[str, ActivityRun] = {}

    def add(self, run: ActivityRun) -> None:
        self._runs[run.run_id] = run

    def remove(self, run_id: str) -> None:
        self._runs.pop(run_id, None)

    def get(self, run_id: str) -> ActivityRun:
        """Return the run with this id.

        Raises:
            ActiveRunNotFoundError: When this process tracks no run with this id.

        """
        try:
            return self._runs[run_id]
        except KeyError:
            raise ActiveRunNotFoundError(f"No active repository run {run_id} in this process") from None


class RepositoryActivity:
    """Starts, renews and finishes the runs that work on repositories."""

    def __init__(
        self,
        cache: InfrahubCache,
        active_runs: ActiveRuns,
        worker_id: str,
        now: Callable[[], datetime],
        sleep: Callable[[float], Awaitable[None]],
        run_ttl_seconds: int,
        renew_interval_seconds: float,
        last_run_ttl_seconds: int,
    ) -> None:
        self._cache = cache
        self._active_runs = active_runs
        self._worker_id = worker_id
        self._now = now
        self._sleep = sleep
        self._run_ttl_seconds = run_ttl_seconds
        self._renew_interval_seconds = renew_interval_seconds
        self._last_run_ttl_seconds = last_run_ttl_seconds
        # The event loop keeps only weak references to tasks, so a cleanup that outlives its caller is held here.
        self._cleanups: set[asyncio.Task[None]] = set()

    @asynccontextmanager
    async def track(self, repository_id: str, operation: RepositoryActivityOperation) -> AsyncIterator[ActivityRun]:
        """Keep a run record in the cache while the body runs, and replace it with the last run when the body ends.

        The record is removed however the body ends, including on failure and cancellation. The cleanup runs to
        its end even when the caller is cancelled again while it waits for it.
        """
        started_at = self._now()
        run = ActivityRun(
            cache=self._cache,
            record=ActivityRunRecord(
                run_id=str(uuid.uuid4()),
                repository_id=repository_id,
                operation=operation,
                phase=None,
                branch_name=None,
                worker_id=self._worker_id,
                started_at=started_at,
                updated_at=started_at,
            ),
            now=self._now,
            ttl_seconds=self._run_ttl_seconds,
        )
        self._active_runs.add(run)
        renewal: asyncio.Task[None] | None = None
        try:
            await run.renew()
            renewal = asyncio.create_task(self._renew(run=run))
            yield run
        finally:
            # Nothing before the first await, so a repeated cancellation cannot skip these.
            self._active_runs.remove(run.run_id)
            if renewal is not None:
                renewal.cancel()
            cleanup = asyncio.create_task(self._finish(run=run, renewal=renewal))
            self._cleanups.add(cleanup)
            cleanup.add_done_callback(self._cleanups.discard)
            await asyncio.shield(cleanup)

    async def _finish(self, run: ActivityRun, renewal: asyncio.Task[None] | None) -> None:
        if renewal is not None:
            # The renewal must be gone before the delete, or a late renewal writes the record again.
            await asyncio.gather(renewal, return_exceptions=True)
        await run.finish(last_run_ttl_seconds=self._last_run_ttl_seconds)

    async def _renew(self, run: ActivityRun) -> None:
        while True:
            await self._sleep(self._renew_interval_seconds)
            await run.renew()
