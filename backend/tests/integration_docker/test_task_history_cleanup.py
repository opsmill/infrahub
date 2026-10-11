from __future__ import annotations

import json
import re
import time
from subprocess import CalledProcessError  # noqa: S404 - the error a failed command in a container raises
from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk.testing.docker import TestInfrahubDockerClient

if TYPE_CHECKING:
    from collections.abc import Iterator

    from infrahub_testcontainers.container import InfrahubDockerCompose

pytestmark = pytest.mark.shard_a

OLD_RUNS = 300
SCENARIO_DELETED_RUNS = 8
TASK_HISTORY_TABLES = ("flow_run", "flow_run_state", "task_run", "task_run_state", "log", "artifact")
ACTIVITY_LOG_TABLES = ("events", "event_resources")
LOG_LOCK_HOLDER = "task-history-cleanup-test-log-lock"
# A key of the test's own, so a cleanup that another test runs on the shared stack never holds it.
ADVISORY_LOCK_KEY = int.from_bytes(b"locktest", byteorder="big")
# Long enough to outwait autovacuum and Prefect's own writes, far shorter than the hold on the locked table.
REWRITE_LOCK_TIMEOUT_SECONDS = 5
OLD_RUN_AGE_DAYS = 35
RECENT_RUN_AGE_DAYS = 5
# Far more rows than the stack's own runs hold, so their freed space is most of the runs table whatever ran before.
RUNS_DELETED_BEFORE_THE_CLEANUP = 2000
# Inserted after the deleted runs, so that a vacuum cannot cut the space they freed off the end of the table.
RUNS_AFTER_THE_DELETED_ONES = 20
# Small enough that a runs table of the test's inserted runs is measured from a sample of its pages.
EXACT_MEASURE_PAGES = 100
FILLER_LOG_NAME = "task-history-cleanup-test-filler"
# The bytes a filler log takes, roughly, so that the fillers can outweigh whatever the log table already holds.
FILLER_LOG_BYTES = 600

# Only the task manager container reaches its database; the image ships the test helpers under /source/backend.
_SEED_SCRIPT = f"""
import asyncio, json, sys
sys.path.insert(0, "/source/backend")
from prefect.server.database import provide_database_interface
from tests.helpers.task_manager_seed import seed_task_history

async def main():
    seeded = await seed_task_history(db=provide_database_interface(), old_runs={OLD_RUNS})
    print(json.dumps({{"kept": seeded.kept.to_json(), "deleted": seeded.deleted.to_json()}}))

asyncio.run(main())
"""

_READ_SCRIPT = """
import asyncio, json, sys
sys.path.insert(0, "/source/backend")
from prefect.server.database import provide_database_interface
from tests.helpers.task_manager_seed import read_task_history_ids

async def main():
    print(json.dumps((await read_task_history_ids(db=provide_database_interface())).to_json()))

asyncio.run(main())
"""

# A cleanup that rewrites the given tables only, so the outcome does not depend on what else the stack stored.
_CLEANUP_OF_TABLES_SCRIPT = f"""
import asyncio, sys
from datetime import UTC, datetime, timedelta
sys.path.insert(0, "/source/backend")
from prefect.server.database import provide_database_interface
from prefect.server.utilities.database import get_max_query_parameters
from infrahub.prefect_server.task_history import PostgresTableRewriter, TaskHistoryCleanup, TaskHistoryTables
from infrahub.prefect_server.task_history_models import CleanupJob, CleanupJobState, CleanupRewrite

async def main(tables):
    db = provide_database_interface()
    job = CleanupJob(
        id="tables-of-the-test",
        state=CleanupJobState.RUNNING,
        rewrite=CleanupRewrite.IF_FREED,
        cutoff=datetime.now(UTC) - timedelta(days=30),
    )
    cleanup = TaskHistoryCleanup(
        tables=TaskHistoryTables(db=db, ids_per_statement=get_max_query_parameters()),
        rewriter=PostgresTableRewriter(
            db=db,
            tables=tables,
            exact_measure_pages={EXACT_MEASURE_PAGES},
            lock_timeout=timedelta(seconds={REWRITE_LOCK_TIMEOUT_SECONDS}),
            retries=0,
        ),
    )
    await cleanup.delete(job=job)
    await cleanup.rewrite(job=job, mode=job.rewrite)
    print(job.model_dump_json())

asyncio.run(main(tables=tuple(sys.argv[1:])))
"""

_INSERT_FILLER_LOGS_SCRIPT = f"""
import asyncio, sys
from datetime import UTC, datetime
import sqlalchemy as sa
from prefect.server.database import provide_database_interface

async def main(logs):
    db = provide_database_interface()
    now = datetime.now(UTC)
    row = {{"name": "{FILLER_LOG_NAME}", "level": 20, "message": "x" * 500, "timestamp": now}}
    async with db.session_context(begin_transaction=True) as session:
        await session.execute(sa.insert(db.Log), [row] * logs)
    print(logs)

asyncio.run(main(logs=int(sys.argv[1])))
"""

_TASK_HISTORY_SIZE_SCRIPT = """
import asyncio, json
import httpx

async def main():
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get("http://localhost:4200/api/infrahub/task-history/size")
        response.raise_for_status()
    print(json.dumps(response.json()))

asyncio.run(main())
"""

# Plain SQL through Prefect's own tables, so the script also runs in an image of an earlier cleanup.
_INSERT_RUNS_SCRIPT = """
import asyncio, sys
from datetime import UTC, datetime, timedelta
from uuid import uuid4
import sqlalchemy as sa
from prefect.server.database import provide_database_interface
from prefect.server.schemas.states import StateType

async def main(runs, ended_days_ago):
    db = provide_database_interface()
    flow_id = uuid4()
    end_time = datetime.now(UTC) - timedelta(days=ended_days_ago)
    async with db.session_context(begin_transaction=True) as session:
        await session.execute(sa.insert(db.Flow).values(id=flow_id, name=f"flow-{flow_id}"))
        await session.execute(
            sa.insert(db.FlowRun),
            [
                {
                    "flow_id": flow_id,
                    "state_type": StateType.COMPLETED,
                    "state_name": "Completed",
                    "start_time": end_time - timedelta(hours=1),
                    "end_time": end_time,
                }
                for _ in range(runs)
            ],
        )
    print(flow_id)

asyncio.run(main(runs=int(sys.argv[1]), ended_days_ago=int(sys.argv[2])))
"""

_ADVISORY_LOCK_SCRIPT = f"""
import asyncio, json, sys
sys.path.insert(0, "/source/backend")
from prefect.server.database import provide_database_interface
from infrahub.prefect_server.task_history import PostgresAdvisoryLock

async def main():
    db = provide_database_interface()
    first, second, third = (PostgresAdvisoryLock(db=db, key={ADVISORY_LOCK_KEY}) for _ in range(3))
    acquired = [await first.try_acquire(), await second.try_acquire()]
    await first.release()
    acquired.append(await second.try_acquire())
    await second.release()
    acquired.append(await third.try_acquire())
    await third.release()
    print(json.dumps(acquired))

asyncio.run(main())
"""

# The queries below interpolate only this module's constants, so S608 has no input to guard against.
_TABLE_NAMES = f"ARRAY[{', '.join(f"'{table}'" for table in TASK_HISTORY_TABLES)}]"
_SIZE_QUERY = f"SELECT sum(pg_total_relation_size(name::regclass)) FROM unnest({_TABLE_NAMES}) AS name"  # noqa: S608
_ALL_TABLE_NAMES = f"ARRAY[{', '.join(f"'{table}'" for table in TASK_HISTORY_TABLES + ACTIVITY_LOG_TABLES)}]"
_FILE_NODES_QUERY = (
    f"SELECT relname || '=' || relfilenode FROM pg_class WHERE relkind = 'r' AND relname = ANY({_ALL_TABLE_NAMES})"  # noqa: S608
)
_DELETE_FILLER_LOGS_QUERY = f"DELETE FROM log WHERE name = '{FILLER_LOG_NAME}'"  # noqa: S608
_LOG_LOCK_QUERY = (
    "SELECT count(*) FROM pg_locks JOIN pg_stat_activity USING (pid) "  # noqa: S608
    f"WHERE application_name = '{LOG_LOCK_HOLDER}' AND relation = 'log'::regclass AND granted"
)
_RELEASE_LOG_LOCK_QUERY = (
    f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = '{LOG_LOCK_HOLDER}'"  # noqa: S608
)

_DELETED_RUNS = re.compile(r"Deleted (?P<count>\d+) runs that ended before \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC")
_REWRITE_OUTCOMES = {
    "rewritten": re.compile(r"Rewrote (?P<tables>.+)$"),
    "mostly_live": re.compile(
        r"Left (?P<tables>.+) as they are, because their live rows hold at least half of their disk space$"
    ),
    "not_rewritten": re.compile(r"Did not rewrite (?P<tables>.+), which stayed locked by other sessions$"),
}


def _run_in_container(compose: InfrahubDockerCompose, service: str, command: list[str]) -> str:
    """Run the command in the service's container, returning its standard output.

    Raises:
        CalledProcessError: When the command fails, noting what it printed.

    """
    try:
        stdout, _, _ = compose.exec_in_container(command=command, service_name=service)
    except CalledProcessError as exc:
        exc.add_note(f"stdout:\n{exc.stdout.decode()}\nstderr:\n{exc.stderr.decode()}")
        raise
    return stdout


def _python_in_task_manager(compose: InfrahubDockerCompose, script: str, arguments: tuple[str, ...] = ()) -> str:
    stdout = _run_in_container(compose=compose, service="task-manager", command=["python", "-c", script, *arguments])
    return stdout.strip().splitlines()[-1]


def _insert_finished_runs(compose: InfrahubDockerCompose, runs: int, ended_days_ago: int) -> str:
    """Insert finished top-level runs of a flow of their own, returning the id of that flow."""
    return _python_in_task_manager(
        compose=compose, script=_INSERT_RUNS_SCRIPT, arguments=(str(runs), str(ended_days_ago))
    )


def _clean_tables(compose: InfrahubDockerCompose, tables: tuple[str, ...]) -> dict[str, Any]:
    """Run a cleanup that rewrites each of the tables that is mostly free space, returning the job once it ended."""
    job: dict[str, Any] = json.loads(
        _python_in_task_manager(compose=compose, script=_CLEANUP_OF_TABLES_SCRIPT, arguments=tables)
    )
    return job


def _free_most_of_the_runs_table(compose: InfrahubDockerCompose) -> None:
    """Insert and delete far more runs than the stack stores, ahead of a few kept runs that a vacuum cannot cut off."""
    old_flow = _insert_finished_runs(
        compose=compose, runs=RUNS_DELETED_BEFORE_THE_CLEANUP, ended_days_ago=OLD_RUN_AGE_DAYS
    )
    _insert_finished_runs(compose=compose, runs=RUNS_AFTER_THE_DELETED_ONES, ended_days_ago=RECENT_RUN_AGE_DAYS)
    deleted = _query_task_manager_database(
        compose=compose,
        query=f"DELETE FROM flow_run WHERE flow_id = '{old_flow}'",  # noqa: S608 - a flow id the test inserted
    )
    assert deleted == [f"DELETE {RUNS_DELETED_BEFORE_THE_CLEANUP}"]


def _free_most_of_the_log_table(compose: InfrahubDockerCompose) -> None:
    """Insert and delete filler logs that take three times the space the log table already takes."""
    [log_bytes] = _query_task_manager_database(compose=compose, query="SELECT pg_relation_size('log')")
    logs = max(1000, 3 * int(log_bytes) // FILLER_LOG_BYTES)
    _python_in_task_manager(compose=compose, script=_INSERT_FILLER_LOGS_SCRIPT, arguments=(str(logs),))
    assert _query_task_manager_database(compose=compose, query=_DELETE_FILLER_LOGS_QUERY) == [f"DELETE {logs}"]


def _rewrite_outcomes(stdout: str) -> dict[str, list[str]]:
    """The tables each rewrite line of the command names, by outcome."""
    outcomes: dict[str, list[str]] = {outcome: [] for outcome in _REWRITE_OUTCOMES}
    for line in stdout.splitlines():
        for outcome, pattern in _REWRITE_OUTCOMES.items():
            if match := pattern.search(line.strip()):
                outcomes[outcome].extend(match["tables"].split(", "))
    return outcomes


def _query_task_manager_database(compose: InfrahubDockerCompose, query: str) -> list[str]:
    stdout = _run_in_container(
        compose=compose,
        service="task-manager-db",
        command=["psql", "--username=postgres", "--dbname=prefect", "--tuples-only", "--no-align", "-c", query],
    )
    return stdout.strip().splitlines()


def _task_history_size(compose: InfrahubDockerCompose) -> int:
    [size] = _query_task_manager_database(compose=compose, query=_SIZE_QUERY)
    return int(size)


def _file_nodes(compose: InfrahubDockerCompose) -> dict[str, str]:
    """The file each task history table is stored in, which a rewrite replaces."""
    return dict(line.split("=") for line in _query_task_manager_database(compose=compose, query=_FILE_NODES_QUERY))


def _ids_by_table(ids: dict[str, list[str]]) -> dict[str, set[str]]:
    return {table: set(values) for table, values in ids.items()}


class TestTaskHistoryCleanup(TestInfrahubDockerClient):
    @pytest.fixture
    def log_table_locked(
        self,
        infrahub_app: dict[str, int],
        infrahub_compose: InfrahubDockerCompose,
    ) -> Iterator[None]:
        """The log table locked by another session until the test ends, in a mode that a rewrite waits for.

        Raises:
            TimeoutError: When the lock does not show within a minute.

        """
        infrahub_compose._run_command(
            cmd=[
                *infrahub_compose.compose_command_property,
                "exec",
                "--detach",
                "-T",
                "--env",
                f"PGAPPNAME={LOG_LOCK_HOLDER}",
                "task-manager-db",
                "psql",
                "--username=postgres",
                "--dbname=prefect",
                "-c",
                "BEGIN; LOCK TABLE log IN ACCESS SHARE MODE; SELECT pg_sleep(600); COMMIT;",
            ]
        )
        # The session outlives a failed wait as well, holding the lock for minutes unless it is ended.
        try:
            deadline = time.monotonic() + 60
            while _query_task_manager_database(compose=infrahub_compose, query=_LOG_LOCK_QUERY) != ["1"]:
                if time.monotonic() > deadline:
                    raise TimeoutError(f"{LOG_LOCK_HOLDER} did not lock the log table within 60 seconds")
                time.sleep(0.5)
            yield
        finally:
            _query_task_manager_database(compose=infrahub_compose, query=_RELEASE_LOG_LOCK_QUERY)

    def test_the_task_manager_measures_the_disk_space_of_the_task_history(
        self,
        infrahub_app: dict[str, int],
        infrahub_compose: InfrahubDockerCompose,
    ) -> None:
        """The task manager answers the disk space of the task history tables with their indexes, as Postgres measures it."""
        # Only writes happen on the stack meanwhile, and they only grow the tables before anything is deleted.
        before = _task_history_size(compose=infrahub_compose)
        answer = json.loads(_python_in_task_manager(compose=infrahub_compose, script=_TASK_HISTORY_SIZE_SCRIPT))
        after = _task_history_size(compose=infrahub_compose)

        assert list(answer) == ["size"]
        assert before <= answer["size"] <= after

    def test_flush_flow_runs_with_rewrite_deletes_the_old_task_history_and_reports_each_table(
        self,
        infrahub_app: dict[str, int],
        infrahub_compose: InfrahubDockerCompose,
    ) -> None:
        """On Postgres the command deletes old finished runs with their children, keeps the rest, and reports every table."""
        seeded = json.loads(_python_in_task_manager(compose=infrahub_compose, script=_SEED_SCRIPT))
        kept, deleted = _ids_by_table(ids=seeded["kept"]), _ids_by_table(ids=seeded["deleted"])

        stdout = _run_in_container(
            compose=infrahub_compose,
            service="infrahub-server",
            command=["env", "COLUMNS=500", "infrahub", "tasks", "flush", "flow-runs", "--rewrite"],
        )

        remaining = _ids_by_table(
            ids=json.loads(_python_in_task_manager(compose=infrahub_compose, script=_READ_SCRIPT))
        )
        reported = [table for tables in _rewrite_outcomes(stdout=stdout).values() for table in tables]
        assert {table: remaining[table] & (kept[table] | deleted[table]) for table in kept} == kept
        assert len(deleted["flow_runs"]) == OLD_RUNS + SCENARIO_DELETED_RUNS
        assert [int(match["count"]) for match in _DELETED_RUNS.finditer(stdout)] == [OLD_RUNS + SCENARIO_DELETED_RUNS]
        assert sorted(reported) == sorted(TASK_HISTORY_TABLES + ACTIVITY_LOG_TABLES)

    def test_a_cleanup_rewrites_a_table_freed_before_it_started_and_leaves_a_mostly_live_one(
        self,
        infrahub_app: dict[str, int],
        infrahub_compose: InfrahubDockerCompose,
    ) -> None:
        """A cleanup returns the space of runs deleted before it, as at a restart, and leaves a mostly live table alone.

        Both tables are measured from a sample of their pages when they hold more pages than the test allows.
        """
        _free_most_of_the_runs_table(compose=infrahub_compose)
        # Packs the events, so that whatever was deleted from them before does not count as free space.
        compacted = _query_task_manager_database(compose=infrahub_compose, query="VACUUM FULL events")
        file_nodes_before = _file_nodes(compose=infrahub_compose)

        job = _clean_tables(compose=infrahub_compose, tables=("flow_run", "events"))

        file_nodes_after = _file_nodes(compose=infrahub_compose)
        assert compacted == ["VACUUM"]
        assert (job["rewritten"], job["mostly_live"], job["not_rewritten"]) == (["flow_run"], ["events"], [])
        assert {table for table in file_nodes_before if file_nodes_after[table] != file_nodes_before[table]} == {
            "flow_run"
        }

    def test_the_cleanup_lock_has_one_holder_at_a_time_until_it_is_released(
        self,
        infrahub_app: dict[str, int],
        infrahub_compose: InfrahubDockerCompose,
    ) -> None:
        """A second lock on the key is refused while the first holds it, and taken once the holder releases it."""
        acquired = json.loads(_python_in_task_manager(compose=infrahub_compose, script=_ADVISORY_LOCK_SCRIPT))

        assert acquired == [True, False, True, True]

    @pytest.mark.usefixtures("log_table_locked")
    def test_a_table_locked_past_the_lock_timeout_is_left_out_of_the_rewrite(
        self, infrahub_compose: InfrahubDockerCompose
    ) -> None:
        """A freed table kept locked past the lock timeout is reported not rewritten, and the next table is rewritten."""
        _free_most_of_the_log_table(compose=infrahub_compose)
        _free_most_of_the_runs_table(compose=infrahub_compose)
        file_nodes_before = _file_nodes(compose=infrahub_compose)

        job = _clean_tables(compose=infrahub_compose, tables=("log", "flow_run"))

        file_nodes_after = _file_nodes(compose=infrahub_compose)
        assert (job["rewritten"], job["mostly_live"], job["not_rewritten"]) == (["flow_run"], [], ["log"])
        assert sorted(file_nodes_before) == sorted(TASK_HISTORY_TABLES + ACTIVITY_LOG_TABLES)
        assert {table for table in file_nodes_before if file_nodes_after[table] != file_nodes_before[table]} == {
            "flow_run"
        }
