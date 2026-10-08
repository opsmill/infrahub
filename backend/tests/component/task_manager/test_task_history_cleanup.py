from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from prefect.server.schemas.states import StateType
from prefect.server.services.db_vacuum import vacuum_old_flow_runs
from prefect.settings import temporary_settings
from tests.adapters.task_history import RecordingRewriter
from tests.helpers.task_manager_seed import (
    copy_task_manager_database,
    days_ago,
    read_task_history_ids,
    seed_flow_run,
    seed_task_history,
    task_manager_database,
)

from infrahub.prefect_server.task_history import (
    TableSpace,
    TaskHistoryCleanup,
    TaskHistoryTables,
    build_task_history_cleanup,
)
from infrahub.prefect_server.task_history_models import CleanupJob, CleanupJobState, CleanupRewrite

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

RETENTION = timedelta(days=30)
# Old runs that all ended on one day, so a day's delete spans several statements when a statement takes one run.
RUNS_ENDED_ON_ONE_DAY = 3


@pytest.fixture
def thirty_day_retention() -> Generator[None, None, None]:
    with temporary_settings(updates={"server.services.db_vacuum.retention_period": RETENTION}):
        yield


def _job(rewrite: CleanupRewrite = CleanupRewrite.NEVER) -> CleanupJob:
    return CleanupJob(id="test", state=CleanupJobState.RUNNING, rewrite=rewrite, cutoff=datetime.now(UTC) - RETENTION)


@dataclass
class StatementSizeCase:
    name: str
    ids_per_statement: int


STATEMENT_SIZE_CASES: list[StatementSizeCase] = [
    StatementSizeCase(name="one_run_per_statement", ids_per_statement=1),
    StatementSizeCase(name="as_many_runs_as_sqlite_takes", ids_per_statement=999),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in STATEMENT_SIZE_CASES])
@pytest.mark.usefixtures("thirty_day_retention")
async def test_cleanup_leaves_the_task_history_prefect_leaves(
    task_manager_database_path: Path, case: StatementSizeCase
) -> None:
    """The cleanup leaves the same task history as Prefect's vacuum of old flow runs, however many runs a statement takes."""
    prefect_db = task_manager_database(task_manager_database_path)
    seeded = await seed_task_history(db=prefect_db, old_runs=RUNS_ENDED_ON_ONE_DAY)
    copy_path = task_manager_database_path.with_name("copy.db")
    copy_task_manager_database(source=task_manager_database_path, target=copy_path)
    cleanup_db = task_manager_database(copy_path)
    cleanup = TaskHistoryCleanup(
        tables=TaskHistoryTables(db=cleanup_db, ids_per_statement=case.ids_per_statement), rewriter=None
    )
    job = _job()

    await vacuum_old_flow_runs(db=prefect_db)
    await cleanup.delete(job=job)

    left_by_prefect = await read_task_history_ids(db=prefect_db)
    left_by_cleanup = await read_task_history_ids(db=cleanup_db)
    assert left_by_cleanup == left_by_prefect
    assert left_by_cleanup == seeded.kept
    assert job.deleted_runs == len(seeded.deleted.flow_runs) == 11


async def test_cleanup_keeps_a_run_that_ended_after_the_cutoff_on_the_cutoff_day(
    task_manager_database_path: Path,
) -> None:
    """On the cutoff's day, a run that ended before the cutoff is deleted and one that ended after it is kept."""
    db = task_manager_database(task_manager_database_path)
    cutoff = datetime(2026, 1, 15, 12, tzinfo=UTC)
    await seed_flow_run(
        db=db,
        state_type=StateType.COMPLETED,
        start_time=datetime(2026, 1, 15, 5, tzinfo=UTC),
        end_time=datetime(2026, 1, 15, 6, tzinfo=UTC),
    )
    ended_after_the_cutoff = await seed_flow_run(
        db=db,
        state_type=StateType.COMPLETED,
        start_time=datetime(2026, 1, 15, 17, tzinfo=UTC),
        end_time=datetime(2026, 1, 15, 18, tzinfo=UTC),
    )
    job = CleanupJob(id="test", state=CleanupJobState.RUNNING, rewrite=CleanupRewrite.NEVER, cutoff=cutoff)

    await TaskHistoryCleanup(tables=TaskHistoryTables(db=db, ids_per_statement=999), rewriter=None).delete(job=job)

    assert (await read_task_history_ids(db=db)).flow_runs == {ended_after_the_cutoff.id}
    assert (job.deleted_runs, job.current_day) == (1, date(2026, 1, 15))


@pytest.mark.usefixtures("thirty_day_retention")
async def test_cleanup_and_prefect_vacuum_running_together_leave_the_same_task_history(
    task_manager_database_path: Path,
) -> None:
    """The cleanup and Prefect's vacuum of old flow runs both succeed on the same runs and leave the old runs deleted."""
    db = task_manager_database(task_manager_database_path)
    seeded = await seed_task_history(db=db)
    job = _job()

    with temporary_settings(updates={"server.services.db_vacuum.batch_size": 1}):
        await asyncio.gather(vacuum_old_flow_runs(db=db), build_task_history_cleanup(db=db).delete(job=job))

    assert await read_task_history_ids(db=db) == seeded.kept


@dataclass
class RewriteDecisionCase:
    name: str
    rewrite: CleanupRewrite
    old_runs: int
    flow_run_space: TableSpace
    expected_rewritten: bool
    expected_calls: list[str]
    expected_not_rewritten: list[str]
    expected_size_after: int


REWRITE_DECISION_CASES: list[RewriteDecisionCase] = [
    RewriteDecisionCase(
        name="if_freed_with_more_than_half_of_the_runs_table_free",
        rewrite=CleanupRewrite.IF_FREED,
        old_runs=3,
        flow_run_space=TableSpace(disk_bytes=1000, live_bytes=499),
        expected_rewritten=True,
        expected_calls=["total_size", "flow_run_space", "rewrite", "total_size"],
        expected_not_rewritten=["log"],
        expected_size_after=100,
    ),
    RewriteDecisionCase(
        name="if_freed_with_half_of_the_runs_table_free",
        rewrite=CleanupRewrite.IF_FREED,
        old_runs=3,
        flow_run_space=TableSpace(disk_bytes=1000, live_bytes=500),
        expected_rewritten=False,
        expected_calls=["total_size", "flow_run_space", "total_size"],
        expected_not_rewritten=[],
        expected_size_after=1000,
    ),
    RewriteDecisionCase(
        name="if_freed_with_the_runs_deleted_before_the_cleanup_started",
        rewrite=CleanupRewrite.IF_FREED,
        old_runs=0,
        flow_run_space=TableSpace(disk_bytes=1000, live_bytes=100),
        expected_rewritten=True,
        expected_calls=["total_size", "flow_run_space", "rewrite", "total_size"],
        expected_not_rewritten=["log"],
        expected_size_after=100,
    ),
    RewriteDecisionCase(
        name="if_freed_with_runs_deleted_from_a_mostly_live_runs_table",
        rewrite=CleanupRewrite.IF_FREED,
        old_runs=3,
        flow_run_space=TableSpace(disk_bytes=1000, live_bytes=900),
        expected_rewritten=False,
        expected_calls=["total_size", "flow_run_space", "total_size"],
        expected_not_rewritten=[],
        expected_size_after=1000,
    ),
    RewriteDecisionCase(
        name="always_with_a_mostly_live_runs_table",
        rewrite=CleanupRewrite.ALWAYS,
        old_runs=1,
        flow_run_space=TableSpace(disk_bytes=1000, live_bytes=900),
        expected_rewritten=True,
        expected_calls=["total_size", "rewrite", "total_size"],
        expected_not_rewritten=["log"],
        expected_size_after=100,
    ),
    RewriteDecisionCase(
        name="never_with_a_runs_table_holding_no_live_rows",
        rewrite=CleanupRewrite.NEVER,
        old_runs=3,
        flow_run_space=TableSpace(disk_bytes=1000, live_bytes=0),
        expected_rewritten=False,
        expected_calls=["total_size", "total_size"],
        expected_not_rewritten=[],
        expected_size_after=1000,
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in REWRITE_DECISION_CASES])
async def test_tables_are_rewritten_as_the_cleanup_asks(
    task_manager_database_path: Path, case: RewriteDecisionCase
) -> None:
    """The tables are rewritten always, never, or only when more than half of the runs table is free, whoever freed it."""
    db = task_manager_database(task_manager_database_path)
    for _ in range(case.old_runs):
        await seed_flow_run(db=db, state_type=StateType.COMPLETED, start_time=days_ago(41), end_time=days_ago(40))
    rewriter = RecordingRewriter(flow_run_space=case.flow_run_space)
    job = _job(rewrite=case.rewrite)
    cleanup = TaskHistoryCleanup(tables=TaskHistoryTables(db=db, ids_per_statement=999), rewriter=rewriter)

    await cleanup.delete(job=job)
    await cleanup.rewrite(job=job, mode=job.rewrite)

    assert rewriter.calls == case.expected_calls
    assert (job.deleted_runs, job.rewrite, job.rewritten, job.not_rewritten, job.size_before, job.size_after) == (
        case.old_runs,
        case.rewrite,
        case.expected_rewritten,
        case.expected_not_rewritten,
        1000,
        case.expected_size_after,
    )
