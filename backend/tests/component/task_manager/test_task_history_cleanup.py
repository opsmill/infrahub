from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from prefect.server.schemas.states import StateType
from prefect.server.services.db_vacuum import vacuum_old_flow_runs
from prefect.settings import temporary_settings
from tests.helpers.task_manager_seed import (
    TaskHistoryIds,
    copy_task_manager_database,
    days_ago,
    read_task_history_ids,
    seed_flow_run,
    seed_task_history,
    task_manager_database,
)

from infrahub.prefect_server.task_history import (
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
class DeleteSizeCase:
    name: str
    ids_per_statement: int
    runs_per_transaction: int


DELETE_SIZE_CASES: list[DeleteSizeCase] = [
    DeleteSizeCase(name="one_run_per_statement_and_transaction", ids_per_statement=1, runs_per_transaction=1),
    DeleteSizeCase(name="a_day_over_two_transactions", ids_per_statement=999, runs_per_transaction=2),
    DeleteSizeCase(name="a_day_filling_one_transaction", ids_per_statement=999, runs_per_transaction=3),
    DeleteSizeCase(name="as_many_runs_as_sqlite_takes", ids_per_statement=999, runs_per_transaction=1000),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in DELETE_SIZE_CASES])
@pytest.mark.usefixtures("thirty_day_retention")
async def test_cleanup_leaves_the_task_history_prefect_leaves(
    task_manager_database_path: Path, case: DeleteSizeCase
) -> None:
    """The cleanup leaves the task history Prefect's vacuum of old flow runs leaves, whatever its statement and transaction sizes."""
    prefect_db = task_manager_database(task_manager_database_path)
    seeded = await seed_task_history(db=prefect_db, old_runs=RUNS_ENDED_ON_ONE_DAY)
    copy_path = task_manager_database_path.with_name("copy.db")
    copy_task_manager_database(source=task_manager_database_path, target=copy_path)
    cleanup_db = task_manager_database(copy_path)
    cleanup = TaskHistoryCleanup(
        tables=TaskHistoryTables(db=cleanup_db, ids_per_statement=case.ids_per_statement, lock_timeout=None),
        rewriter=None,
        runs_per_transaction=case.runs_per_transaction,
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

    await TaskHistoryCleanup(
        tables=TaskHistoryTables(db=db, ids_per_statement=999, lock_timeout=None),
        rewriter=None,
        runs_per_transaction=1000,
    ).delete(job=job)

    assert (await read_task_history_ids(db=db)).flow_runs == {ended_after_the_cutoff.id}
    assert (job.deleted_runs, job.current_day) == (1, date(2026, 1, 15))


async def test_a_delete_takes_the_earliest_ended_runs_up_to_the_limit(task_manager_database_path: Path) -> None:
    """A delete takes no more runs than its limit, the earliest ended first, whatever order the runs were stored in."""
    db = task_manager_database(task_manager_database_path)
    day = datetime(2026, 1, 10, tzinfo=UTC)
    latest = await seed_flow_run(
        db=db,
        state_type=StateType.COMPLETED,
        start_time=day + timedelta(hours=3),
        end_time=day + timedelta(hours=3, minutes=5),
    )
    for hour in (1, 2):
        await seed_flow_run(
            db=db,
            state_type=StateType.COMPLETED,
            start_time=day + timedelta(hours=hour),
            end_time=day + timedelta(hours=hour, minutes=5),
        )

    deleted = await TaskHistoryTables(db=db, ids_per_statement=999, lock_timeout=None).delete_runs(
        ended_from=day, ended_before=day + timedelta(days=1), limit=2
    )

    assert deleted == 2
    assert await read_task_history_ids(db=db) == TaskHistoryIds(
        flow_runs={latest.id},
        flow_run_states={latest.state_id},
        task_runs=set(latest.task_run_ids),
        task_run_states=set(latest.task_run_state_ids),
    )


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
class CountCase:
    name: str
    limit: int
    expected_count: int


COUNT_CASES: list[CountCase] = [
    CountCase(name="below_the_limit", limit=10, expected_count=3),
    CountCase(name="stopped_at_the_limit", limit=2, expected_count=2),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in COUNT_CASES])
async def test_old_runs_are_counted_as_the_cleanup_selects_them_up_to_the_limit(
    task_manager_database_path: Path, case: CountCase
) -> None:
    """Only finished top-level runs that ended before the cutoff are counted, and counting stops at the limit."""
    db = task_manager_database(task_manager_database_path)
    for _ in range(3):
        await seed_flow_run(db=db, state_type=StateType.COMPLETED, start_time=days_ago(41), end_time=days_ago(40))
    recent = await seed_flow_run(db=db, state_type=StateType.COMPLETED, start_time=days_ago(6), end_time=days_ago(5))
    await seed_flow_run(
        db=db,
        state_type=StateType.COMPLETED,
        start_time=days_ago(41),
        end_time=days_ago(40),
        parent_task_run_id=recent.task_run_ids[0],
    )
    await seed_flow_run(db=db, state_type=StateType.RUNNING, start_time=days_ago(41), end_time=None)
    tables = TaskHistoryTables(db=db, ids_per_statement=999, lock_timeout=None)

    counted = await tables.count_runs(ended_before=datetime.now(UTC) - RETENTION, limit=case.limit)

    assert counted == case.expected_count
