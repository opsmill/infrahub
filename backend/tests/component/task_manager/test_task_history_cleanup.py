from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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
    CleanupJob,
    CleanupJobState,
    CleanupRewrite,
    TaskHistoryCleanup,
    TaskHistoryTables,
    build_task_history_cleanup,
)

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

RETENTION = timedelta(days=30)


@pytest.fixture
def thirty_day_retention() -> Generator[None, None, None]:
    with temporary_settings(updates={"server.services.db_vacuum.retention_period": RETENTION}):
        yield


def _job(rewrite: CleanupRewrite = CleanupRewrite.NEVER) -> CleanupJob:
    return CleanupJob(id="test", state=CleanupJobState.RUNNING, rewrite=rewrite, cutoff=datetime.now(UTC) - RETENTION)


@pytest.mark.usefixtures("thirty_day_retention")
async def test_cleanup_leaves_the_task_history_prefect_leaves(task_manager_database_path: Path) -> None:
    """The cleanup leaves the same runs, task runs, states, logs and artifacts as Prefect's vacuum of old flow runs."""
    prefect_db = task_manager_database(task_manager_database_path)
    seeded = await seed_task_history(db=prefect_db)
    copy_path = task_manager_database_path.with_name("copy.db")
    copy_task_manager_database(source=task_manager_database_path, target=copy_path)
    cleanup_db = task_manager_database(copy_path)
    job = _job()

    await vacuum_old_flow_runs(db=prefect_db)
    await build_task_history_cleanup(db=cleanup_db).delete(job=job)

    left_by_prefect = await read_task_history_ids(db=prefect_db)
    left_by_cleanup = await read_task_history_ids(db=cleanup_db)
    assert left_by_cleanup == left_by_prefect
    assert left_by_cleanup == seeded.kept
    assert job.deleted_runs == len(seeded.deleted.flow_runs) == 8


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
    recent_runs: int
    expected_rewritten: bool
    expected_calls: list[str]
    expected_not_rewritten: list[str]
    expected_size_after: int


REWRITE_DECISION_CASES: list[RewriteDecisionCase] = [
    RewriteDecisionCase(
        name="if_freed_with_more_than_half_of_the_runs_deleted",
        rewrite=CleanupRewrite.IF_FREED,
        old_runs=3,
        recent_runs=2,
        expected_rewritten=True,
        expected_calls=["total_size", "rewrite", "total_size"],
        expected_not_rewritten=["log"],
        expected_size_after=100,
    ),
    RewriteDecisionCase(
        name="if_freed_with_half_of_the_runs_deleted",
        rewrite=CleanupRewrite.IF_FREED,
        old_runs=2,
        recent_runs=2,
        expected_rewritten=False,
        expected_calls=["total_size", "total_size"],
        expected_not_rewritten=[],
        expected_size_after=1000,
    ),
    RewriteDecisionCase(
        name="always_with_a_fifth_of_the_runs_deleted",
        rewrite=CleanupRewrite.ALWAYS,
        old_runs=1,
        recent_runs=4,
        expected_rewritten=True,
        expected_calls=["total_size", "rewrite", "total_size"],
        expected_not_rewritten=["log"],
        expected_size_after=100,
    ),
    RewriteDecisionCase(
        name="never_with_every_run_deleted",
        rewrite=CleanupRewrite.NEVER,
        old_runs=3,
        recent_runs=0,
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
    """The tables are rewritten always, never, or only when the deletes freed more than half of the runs they held."""
    db = task_manager_database(task_manager_database_path)
    for _ in range(case.old_runs):
        await seed_flow_run(db=db, state_type=StateType.COMPLETED, start_time=days_ago(41), end_time=days_ago(40))
    for _ in range(case.recent_runs):
        await seed_flow_run(db=db, state_type=StateType.COMPLETED, start_time=days_ago(6), end_time=days_ago(5))
    rewriter = RecordingRewriter()
    job = _job(rewrite=case.rewrite)
    cleanup = TaskHistoryCleanup(tables=TaskHistoryTables(db=db, ids_per_statement=999), rewriter=rewriter)

    runs_before = await cleanup.delete(job=job)
    await cleanup.rewrite(job=job, mode=job.rewrite, runs_before=runs_before)

    assert rewriter.calls == case.expected_calls
    assert (job.deleted_runs, job.rewrite, job.rewritten, job.not_rewritten, job.size_before, job.size_after) == (
        case.old_runs,
        case.rewrite,
        case.expected_rewritten,
        case.expected_not_rewritten,
        1000,
        case.expected_size_after,
    )
