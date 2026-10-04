from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
import sqlalchemy as sa
from prefect.server.schemas.states import StateType
from prefect.server.services.db_vacuum import vacuum_old_flow_runs
from prefect.settings import temporary_settings
from tests.helpers.task_manager_seed import (
    SeededFlowRun,
    copy_task_manager_database,
    seed_artifact,
    seed_flow_run,
    seed_log,
    task_manager_database,
)

from infrahub.prefect_server.task_history import (
    CleanupJob,
    CleanupJobState,
    TaskHistoryCleanup,
    TaskHistoryTables,
    build_task_history_cleanup,
)

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path
    from uuid import UUID

    from prefect.server.database import PrefectDBInterface

RETENTION = timedelta(days=30)


@dataclass
class TaskHistoryIds:
    flow_runs: set[UUID] = field(default_factory=set)
    flow_run_states: set[UUID] = field(default_factory=set)
    task_runs: set[UUID] = field(default_factory=set)
    task_run_states: set[UUID] = field(default_factory=set)
    logs: set[UUID] = field(default_factory=set)
    artifacts: set[UUID] = field(default_factory=set)


@dataclass
class SeededTaskHistory:
    kept: TaskHistoryIds = field(default_factory=TaskHistoryIds)
    deleted: TaskHistoryIds = field(default_factory=TaskHistoryIds)


class RecordingRewriter:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def total_size(self) -> int:
        self.calls.append("total_size")
        return 1000 if "rewrite" not in self.calls else 100

    async def rewrite(self) -> list[str]:
        self.calls.append("rewrite")
        return ["log"]


@pytest.fixture
def thirty_day_retention() -> Generator[None, None, None]:
    with temporary_settings(updates={"server.services.db_vacuum.retention_period": RETENTION}):
        yield


def _days_ago(days: int, hour: int = 12) -> datetime:
    start_of_today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return start_of_today - timedelta(days=days) + timedelta(hours=hour)


async def _seed_run(
    db: PrefectDBInterface,
    ids: TaskHistoryIds,
    state_type: StateType,
    start_time: datetime | None,
    end_time: datetime | None,
    parent_task_run_id: UUID | None = None,
) -> SeededFlowRun:
    run = await seed_flow_run(
        db=db, state_type=state_type, start_time=start_time, end_time=end_time, parent_task_run_id=parent_task_run_id
    )
    ids.flow_runs.add(run.id)
    ids.flow_run_states.add(run.state_id)
    ids.task_runs.update(run.task_run_ids)
    ids.task_run_states.update(run.task_run_state_ids)
    ids.logs.add(await seed_log(db=db, flow_run_id=run.id))
    ids.logs.add(await seed_log(db=db, flow_run_id=run.id, task_run_id=run.task_run_ids[0]))
    ids.artifacts.add(await seed_artifact(db=db, flow_run_id=run.id, task_run_id=run.task_run_ids[1]))
    return run


async def _seed_task_history(db: PrefectDBInterface) -> SeededTaskHistory:
    seeded = SeededTaskHistory()
    deleted, kept = seeded.deleted, seeded.kept

    for days, state_type in [
        (40, StateType.COMPLETED),
        (41, StateType.FAILED),
        (42, StateType.CANCELLED),
        (43, StateType.CRASHED),
    ]:
        await _seed_run(
            db=db, ids=deleted, state_type=state_type, start_time=_days_ago(days, hour=10), end_time=_days_ago(days)
        )

    parent = await _seed_run(
        db=db, ids=deleted, state_type=StateType.COMPLETED, start_time=_days_ago(47), end_time=_days_ago(45)
    )
    await _seed_run(
        db=db,
        ids=deleted,
        state_type=StateType.COMPLETED,
        start_time=_days_ago(45, hour=10),
        end_time=_days_ago(45, hour=11),
        parent_task_run_id=parent.task_run_ids[0],
    )
    earlier_subflow = await _seed_run(
        db=db,
        ids=deleted,
        state_type=StateType.COMPLETED,
        start_time=_days_ago(47, hour=13),
        end_time=_days_ago(46),
        parent_task_run_id=parent.task_run_ids[1],
    )
    await _seed_run(
        db=db,
        ids=deleted,
        state_type=StateType.FAILED,
        start_time=_days_ago(47, hour=14),
        end_time=_days_ago(47, hour=15),
        parent_task_run_id=earlier_subflow.task_run_ids[0],
    )

    recent = await _seed_run(
        db=db, ids=kept, state_type=StateType.COMPLETED, start_time=_days_ago(5, hour=10), end_time=_days_ago(5)
    )
    running = await _seed_run(db=db, ids=kept, state_type=StateType.RUNNING, start_time=_days_ago(60), end_time=None)
    await _seed_run(db=db, ids=kept, state_type=StateType.PENDING, start_time=None, end_time=None)
    await _seed_run(db=db, ids=kept, state_type=StateType.COMPLETED, start_time=_days_ago(50), end_time=None)
    for parent_task_run_id in (running.task_run_ids[0], recent.task_run_ids[0]):
        await _seed_run(
            db=db,
            ids=kept,
            state_type=StateType.COMPLETED,
            start_time=_days_ago(40, hour=10),
            end_time=_days_ago(40),
            parent_task_run_id=parent_task_run_id,
        )
    return seeded


async def _read_task_history_ids(db: PrefectDBInterface) -> TaskHistoryIds:
    async with db.session_context() as session:
        return TaskHistoryIds(
            flow_runs=set(await session.scalars(sa.select(db.FlowRun.id))),
            flow_run_states=set(await session.scalars(sa.select(db.FlowRunState.id))),
            task_runs=set(await session.scalars(sa.select(db.TaskRun.id))),
            task_run_states=set(await session.scalars(sa.select(db.TaskRunState.id))),
            logs=set(await session.scalars(sa.select(db.Log.id))),
            artifacts=set(await session.scalars(sa.select(db.Artifact.id))),
        )


def _job(rewrite: bool = False) -> CleanupJob:
    return CleanupJob(id="test", state=CleanupJobState.RUNNING, rewrite=rewrite, cutoff=datetime.now(UTC) - RETENTION)


@pytest.mark.usefixtures("thirty_day_retention")
async def test_cleanup_leaves_the_task_history_prefect_leaves(task_manager_database_path: Path) -> None:
    """The cleanup leaves the same runs, task runs, states, logs and artifacts as Prefect's vacuum of old flow runs."""
    prefect_db = task_manager_database(task_manager_database_path)
    seeded = await _seed_task_history(db=prefect_db)
    copy_path = task_manager_database_path.with_name("copy.db")
    copy_task_manager_database(source=task_manager_database_path, target=copy_path)
    cleanup_db = task_manager_database(copy_path)
    job = _job()

    await vacuum_old_flow_runs(db=prefect_db)
    await build_task_history_cleanup(db=cleanup_db).run(job=job)

    left_by_prefect = await _read_task_history_ids(db=prefect_db)
    left_by_cleanup = await _read_task_history_ids(db=cleanup_db)
    assert left_by_cleanup == left_by_prefect
    assert left_by_cleanup == seeded.kept
    assert job.deleted_runs == len(seeded.deleted.flow_runs) == 8


@pytest.mark.usefixtures("thirty_day_retention")
async def test_cleanup_and_prefect_vacuum_running_together_leave_the_same_task_history(
    task_manager_database_path: Path,
) -> None:
    """The cleanup and Prefect's vacuum of old flow runs both succeed on the same runs and leave the old runs deleted."""
    db = task_manager_database(task_manager_database_path)
    seeded = await _seed_task_history(db=db)

    with temporary_settings(updates={"server.services.db_vacuum.batch_size": 1}):
        await asyncio.gather(vacuum_old_flow_runs(db=db), build_task_history_cleanup(db=db).run(job=_job()))

    assert await _read_task_history_ids(db=db) == seeded.kept


@dataclass
class RewriteDecisionCase:
    name: str
    old_runs: int
    recent_runs: int
    expected_rewrite: bool
    expected_calls: list[str]
    expected_not_rewritten: list[str]
    expected_size_after: int


REWRITE_DECISION_CASES: list[RewriteDecisionCase] = [
    RewriteDecisionCase(
        name="more_than_half_of_the_runs_deleted",
        old_runs=3,
        recent_runs=2,
        expected_rewrite=True,
        expected_calls=["total_size", "rewrite", "total_size"],
        expected_not_rewritten=["log"],
        expected_size_after=100,
    ),
    RewriteDecisionCase(
        name="half_of_the_runs_deleted",
        old_runs=2,
        recent_runs=2,
        expected_rewrite=False,
        expected_calls=["total_size", "total_size"],
        expected_not_rewritten=[],
        expected_size_after=1000,
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in REWRITE_DECISION_CASES])
async def test_tables_are_rewritten_only_when_the_deletes_freed_more_than_half_of_the_runs(
    task_manager_database_path: Path, case: RewriteDecisionCase
) -> None:
    """The tables are rewritten only when the cleanup deleted more than half of the runs they held."""
    db = task_manager_database(task_manager_database_path)
    for _ in range(case.old_runs):
        await seed_flow_run(db=db, state_type=StateType.COMPLETED, start_time=_days_ago(41), end_time=_days_ago(40))
    for _ in range(case.recent_runs):
        await seed_flow_run(db=db, state_type=StateType.COMPLETED, start_time=_days_ago(6), end_time=_days_ago(5))
    rewriter = RecordingRewriter()
    job = _job(rewrite=True)

    await TaskHistoryCleanup(tables=TaskHistoryTables(db=db, ids_per_statement=999), rewriter=rewriter).run(job=job)

    assert rewriter.calls == case.expected_calls
    assert (job.deleted_runs, job.rewrite, job.not_rewritten, job.size_before, job.size_after) == (
        case.old_runs,
        case.expected_rewrite,
        case.expected_not_rewritten,
        1000,
        case.expected_size_after,
    )
