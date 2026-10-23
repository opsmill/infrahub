from __future__ import annotations

import os
import sqlite3
import subprocess  # noqa: S404 - Prefect migrates only the database of its process
import sys
from contextlib import closing
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import sqlalchemy as sa
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.database.configurations import AioSqliteConfiguration
from prefect.server.database.orm_models import AioSqliteORMConfiguration
from prefect.server.database.query_components import AioSqliteQueryComponents
from prefect.server.events.schemas.events import ReceivedEvent, RelatedResource, Resource
from prefect.server.events.storage.database import write_events
from prefect.server.schemas.states import StateType
from pydantic_core import to_jsonable_python

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub.events.models import InfrahubEvent


@dataclass(frozen=True)
class SeededFlowRun:
    id: UUID
    state_id: UUID
    task_run_ids: tuple[UUID, ...]
    task_run_state_ids: tuple[UUID, ...]


async def seed_infrahub_event(event: InfrahubEvent, occurred: datetime) -> UUID:
    """Store an Infrahub event in the task manager's database as if it had occurred at the given time."""
    received = ReceivedEvent(
        id=event.meta.id,
        event=event.event_name,
        occurred=occurred,
        resource=Resource(event.get_resource()),
        related=[RelatedResource(item) for item in event.get_related()],
        payload=to_jsonable_python(event.get_event_payload()),
    )
    await _store(events=[received])
    return received.id


async def seed_prefect_event(event_name: str, occurred: datetime) -> UUID:
    """Store a Prefect event about a flow run, with its flow as related item, as if it had occurred at the given time."""
    received = ReceivedEvent(
        id=uuid4(),
        event=event_name,
        occurred=occurred,
        resource=Resource({"prefect.resource.id": f"prefect.flow-run.{uuid4()}"}),
        related=[RelatedResource({"prefect.resource.id": f"prefect.flow.{uuid4()}", "prefect.resource.role": "flow"})],
    )
    await _store(events=[received])
    return received.id


async def _store(events: list[ReceivedEvent]) -> None:
    db = provide_database_interface()
    # Takes the SQLite write lock up front, so a concurrent writer makes the insert wait rather than fail as locked.
    async with db.session_context(begin_transaction=True, with_for_update=True) as session:
        await write_events(session=session, events=events)


def migrate_task_manager_database(path: Path) -> None:
    """Create a SQLite database at the path with Prefect's migrations applied.

    The migrations run in a subprocess, because Prefect binds its migrations to the process-wide database settings.

    Raises:
        RuntimeError: When the migrations fail.

    """
    environment = {name: value for name, value in os.environ.items() if not name.endswith("DATABASE_CONNECTION_URL")}
    environment["PREFECT_SERVER_DATABASE_CONNECTION_URL"] = f"sqlite+aiosqlite:///{path}"
    result = subprocess.run(
        args=[
            sys.executable,
            "-c",
            "import asyncio; from prefect.server.database import provide_database_interface; "
            "asyncio.run(provide_database_interface().create_db())",
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Migrating the task manager database at {path} failed:\n{result.stderr}")


def copy_task_manager_database(source: Path, target: Path) -> None:
    """Copy a SQLite task manager database, including the writes still held in its write-ahead log."""
    with closing(sqlite3.connect(source)) as source_connection, closing(sqlite3.connect(target)) as target_connection:
        source_connection.backup(target_connection)


def task_manager_database(path: Path) -> PrefectDBInterface:
    """Return Prefect's database interface on the SQLite database at the path.

    Raises:
        TypeError: When Prefect builds something other than a database interface.

    """
    db = PrefectDBInterface(
        database_config=AioSqliteConfiguration(connection_url=f"sqlite+aiosqlite:///{path}"),
        query_components=AioSqliteQueryComponents(),
        orm=AioSqliteORMConfiguration(),
    )
    if not isinstance(db, PrefectDBInterface):
        raise TypeError(f"Prefect built a {type(db).__name__} instead of a database interface")
    return db


async def seed_flow_run(
    db: PrefectDBInterface,
    state_type: StateType,
    start_time: datetime | None,
    end_time: datetime | None,
    parent_task_run_id: UUID | None = None,
    task_runs: int = 2,
) -> SeededFlowRun:
    """Store a flow run of a flow of its own, in the given state, with its state row and task runs that each have one.

    Args:
        parent_task_run_id: The task run of the parent flow run, which makes this flow run a subflow.

    """
    flow_run_id = uuid4()
    state_id = uuid4()
    task_run_ids = tuple(uuid4() for _ in range(task_runs))
    task_run_state_ids = tuple(uuid4() for _ in range(task_runs))
    state_name = state_type.value.capitalize()
    async with db.session_context(begin_transaction=True, with_for_update=True) as session:
        flow_id = uuid4()
        await session.execute(sa.insert(db.Flow).values(id=flow_id, name=f"flow-{flow_id}"))
        await session.execute(
            sa.insert(db.FlowRun).values(
                id=flow_run_id,
                flow_id=flow_id,
                state_type=state_type,
                state_name=state_name,
                start_time=start_time,
                end_time=end_time,
                parent_task_run_id=parent_task_run_id,
            )
        )
        await session.execute(
            sa.insert(db.FlowRunState).values(id=state_id, flow_run_id=flow_run_id, type=state_type, name=state_name)
        )
        await session.execute(sa.update(db.FlowRun).where(db.FlowRun.id == flow_run_id).values(state_id=state_id))
        for index, (task_run_id, task_run_state_id) in enumerate(zip(task_run_ids, task_run_state_ids, strict=True)):
            await session.execute(
                sa.insert(db.TaskRun).values(
                    id=task_run_id,
                    flow_run_id=flow_run_id,
                    task_key=f"task-{index}",
                    dynamic_key="0",
                    state_type=state_type,
                    state_name=state_name,
                    start_time=start_time,
                    end_time=end_time,
                    state_id=task_run_state_id,
                )
            )
            await session.execute(
                sa.insert(db.TaskRunState).values(
                    id=task_run_state_id, task_run_id=task_run_id, type=state_type, name=state_name
                )
            )
    return SeededFlowRun(
        id=flow_run_id, state_id=state_id, task_run_ids=task_run_ids, task_run_state_ids=task_run_state_ids
    )


async def seed_log(db: PrefectDBInterface, flow_run_id: UUID, task_run_id: UUID | None = None) -> UUID:
    """Store a log line of the flow run, or of one of its task runs."""
    log_id = uuid4()
    async with db.session_context(begin_transaction=True, with_for_update=True) as session:
        await session.execute(
            sa.insert(db.Log).values(
                id=log_id,
                name="infrahub",
                level=20,
                flow_run_id=flow_run_id,
                task_run_id=task_run_id,
                message="seeded",
                timestamp=datetime.now(UTC),
            )
        )
    return log_id


async def seed_artifact(db: PrefectDBInterface, flow_run_id: UUID, task_run_id: UUID | None = None) -> UUID:
    """Store an artifact of the flow run, or of one of its task runs."""
    artifact_id = uuid4()
    async with db.session_context(begin_transaction=True, with_for_update=True) as session:
        await session.execute(
            sa.insert(db.Artifact).values(
                id=artifact_id, flow_run_id=flow_run_id, task_run_id=task_run_id, type="markdown", data="seeded"
            )
        )
    return artifact_id


@dataclass
class TaskHistoryIds:
    flow_runs: set[UUID] = field(default_factory=set)
    flow_run_states: set[UUID] = field(default_factory=set)
    task_runs: set[UUID] = field(default_factory=set)
    task_run_states: set[UUID] = field(default_factory=set)
    logs: set[UUID] = field(default_factory=set)
    artifacts: set[UUID] = field(default_factory=set)

    def to_json(self) -> dict[str, list[str]]:
        return {name: sorted(str(item) for item in ids) for name, ids in asdict(self).items()}


@dataclass
class SeededTaskHistory:
    kept: TaskHistoryIds = field(default_factory=TaskHistoryIds)
    deleted: TaskHistoryIds = field(default_factory=TaskHistoryIds)


def days_ago(days: int, hour: int = 12) -> datetime:
    """Return the given hour, in UTC, of the day that many days before today."""
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


async def seed_task_history(db: PrefectDBInterface, old_runs: int = 0) -> SeededTaskHistory:
    """Store runs that a cleanup with a 30-day retention deletes, and runs it keeps, each with its children.

    Deleted: top-level runs in each terminal state that ended over 30 days ago, and the subflows of one of them.
    Kept: a recent run, a run still running, a pending run, a finished run with no end time, and old subflows of
    the running and the recent run.

    Args:
        old_runs: More completed runs, ended 35 days ago, that the cleanup deletes.

    """
    seeded = SeededTaskHistory()
    deleted, kept = seeded.deleted, seeded.kept

    for _ in range(old_runs):
        await _seed_run(
            db=db, ids=deleted, state_type=StateType.COMPLETED, start_time=days_ago(35, hour=10), end_time=days_ago(35)
        )

    for days, state_type in [
        (40, StateType.COMPLETED),
        (41, StateType.FAILED),
        (42, StateType.CANCELLED),
        (43, StateType.CRASHED),
    ]:
        await _seed_run(
            db=db, ids=deleted, state_type=state_type, start_time=days_ago(days, hour=10), end_time=days_ago(days)
        )

    parent = await _seed_run(
        db=db, ids=deleted, state_type=StateType.COMPLETED, start_time=days_ago(47), end_time=days_ago(45)
    )
    await _seed_run(
        db=db,
        ids=deleted,
        state_type=StateType.COMPLETED,
        start_time=days_ago(45, hour=10),
        end_time=days_ago(45, hour=11),
        parent_task_run_id=parent.task_run_ids[0],
    )
    earlier_subflow = await _seed_run(
        db=db,
        ids=deleted,
        state_type=StateType.COMPLETED,
        start_time=days_ago(47, hour=13),
        end_time=days_ago(46),
        parent_task_run_id=parent.task_run_ids[1],
    )
    await _seed_run(
        db=db,
        ids=deleted,
        state_type=StateType.FAILED,
        start_time=days_ago(47, hour=14),
        end_time=days_ago(47, hour=15),
        parent_task_run_id=earlier_subflow.task_run_ids[0],
    )

    recent = await _seed_run(
        db=db, ids=kept, state_type=StateType.COMPLETED, start_time=days_ago(5, hour=10), end_time=days_ago(5)
    )
    running = await _seed_run(db=db, ids=kept, state_type=StateType.RUNNING, start_time=days_ago(60), end_time=None)
    await _seed_run(db=db, ids=kept, state_type=StateType.PENDING, start_time=None, end_time=None)
    await _seed_run(db=db, ids=kept, state_type=StateType.COMPLETED, start_time=days_ago(50), end_time=None)
    for parent_task_run_id in (running.task_run_ids[0], recent.task_run_ids[0]):
        await _seed_run(
            db=db,
            ids=kept,
            state_type=StateType.COMPLETED,
            start_time=days_ago(40, hour=10),
            end_time=days_ago(40),
            parent_task_run_id=parent_task_run_id,
        )
    return seeded


async def read_task_history_ids(db: PrefectDBInterface) -> TaskHistoryIds:
    """Return the ids of every run, task run, state, log and artifact in the database."""
    async with db.session_context() as session:
        return TaskHistoryIds(
            flow_runs=set(await session.scalars(sa.select(db.FlowRun.id))),
            flow_run_states=set(await session.scalars(sa.select(db.FlowRunState.id))),
            task_runs=set(await session.scalars(sa.select(db.TaskRun.id))),
            task_run_states=set(await session.scalars(sa.select(db.TaskRunState.id))),
            logs=set(await session.scalars(sa.select(db.Log.id))),
            artifacts=set(await session.scalars(sa.select(db.Artifact.id))),
        )
