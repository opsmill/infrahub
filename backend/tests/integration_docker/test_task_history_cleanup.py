from __future__ import annotations

import json
import re
import time
from subprocess import CalledProcessError  # noqa: S404 - the error a failed command in a container raises
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.testing.docker import TestInfrahubDockerClient

if TYPE_CHECKING:
    from collections.abc import Iterator

    from infrahub_testcontainers.container import InfrahubDockerCompose

pytestmark = pytest.mark.shard_a

OLD_RUNS = 300
SCENARIO_DELETED_RUNS = 8
TASK_HISTORY_TABLES = ("flow_run", "flow_run_state", "task_run", "task_run_state", "log", "artifact")
LOG_LOCK_HOLDER = "task-history-cleanup-test-log-lock"
# Long enough to outwait autovacuum and Prefect's own writes, far shorter than the hold on the locked table.
REWRITE_LOCK_TIMEOUT_SECONDS = 5

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

_CLEANUP_WITH_SHORT_LOCK_TIMEOUT_SCRIPT = f"""
import asyncio, sys
from datetime import UTC, datetime, timedelta
sys.path.insert(0, "/source/backend")
from prefect.server.database import provide_database_interface
from prefect.server.utilities.database import get_max_query_parameters
from infrahub.prefect_server.task_history import (
    CleanupJob, CleanupJobState, CleanupRewrite, PostgresTableRewriter, TaskHistoryCleanup, TaskHistoryTables
)
from tests.adapters.task_history import UnraisedRewrite
from tests.helpers.task_manager_seed import seed_task_history

async def main():
    db = provide_database_interface()
    await seed_task_history(db=db)
    job = CleanupJob(
        id="locked-log",
        state=CleanupJobState.RUNNING,
        rewrite=CleanupRewrite.ALWAYS,
        cutoff=datetime.now(UTC) - timedelta(days=30),
    )
    cleanup = TaskHistoryCleanup(
        tables=TaskHistoryTables(db=db, ids_per_statement=get_max_query_parameters()),
        rewriter=PostgresTableRewriter(
            db=db,
            tables={TASK_HISTORY_TABLES!r},
            lock_timeout=timedelta(seconds={REWRITE_LOCK_TIMEOUT_SECONDS}),
            retries=0,
        ),
    )
    await cleanup.run(job=job, settle=UnraisedRewrite(job=job))
    print(job.model_dump_json())

asyncio.run(main())
"""

# The queries below interpolate only this module's constants, so S608 has no input to guard against.
_TABLE_NAMES = f"ARRAY[{', '.join(f"'{table}'" for table in TASK_HISTORY_TABLES)}]"
_SIZE_QUERY = f"SELECT sum(pg_total_relation_size(name::regclass)) FROM unnest({_TABLE_NAMES}) AS name"  # noqa: S608
_FILE_NODES_QUERY = (
    f"SELECT relname || '=' || relfilenode FROM pg_class WHERE relkind = 'r' AND relname = ANY({_TABLE_NAMES})"  # noqa: S608
)
_LOG_LOCK_QUERY = (
    "SELECT count(*) FROM pg_locks JOIN pg_stat_activity USING (pid) "  # noqa: S608
    f"WHERE application_name = '{LOG_LOCK_HOLDER}' AND relation = 'log'::regclass AND granted"
)
_RELEASE_LOG_LOCK_QUERY = (
    f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = '{LOG_LOCK_HOLDER}'"  # noqa: S608
)

_DELETED_RUNS = re.compile(r"Deleted (?P<count>\d+) runs that ended before \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC")


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


def _python_in_task_manager(compose: InfrahubDockerCompose, script: str) -> str:
    stdout = _run_in_container(compose=compose, service="task-manager", command=["python", "-c", script])
    return stdout.strip().splitlines()[-1]


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

    def test_flush_flow_runs_with_rewrite_deletes_the_old_task_history_and_shrinks_its_tables(
        self,
        infrahub_app: dict[str, int],
        infrahub_compose: InfrahubDockerCompose,
    ) -> None:
        """On Postgres the command deletes old finished runs with their children, keeps the rest, and shrinks the tables."""
        seeded = json.loads(_python_in_task_manager(compose=infrahub_compose, script=_SEED_SCRIPT))
        kept, deleted = _ids_by_table(ids=seeded["kept"]), _ids_by_table(ids=seeded["deleted"])
        size_before = _task_history_size(compose=infrahub_compose)

        stdout = _run_in_container(
            compose=infrahub_compose,
            service="infrahub-server",
            command=["infrahub", "tasks", "flush", "flow-runs", "--rewrite"],
        )

        remaining = _ids_by_table(
            ids=json.loads(_python_in_task_manager(compose=infrahub_compose, script=_READ_SCRIPT))
        )
        assert {table: remaining[table] & (kept[table] | deleted[table]) for table in kept} == kept
        assert len(deleted["flow_runs"]) == OLD_RUNS + SCENARIO_DELETED_RUNS
        assert [int(match["count"]) for match in _DELETED_RUNS.finditer(stdout)] == [OLD_RUNS + SCENARIO_DELETED_RUNS]
        assert stdout.strip().splitlines()[-1].strip().endswith("Task history tables rewritten")
        assert _task_history_size(compose=infrahub_compose) < size_before

    @pytest.mark.usefixtures("log_table_locked")
    def test_a_table_locked_past_the_lock_timeout_is_left_out_of_the_rewrite(
        self, infrahub_compose: InfrahubDockerCompose
    ) -> None:
        """A table kept locked past the lock timeout is reported not rewritten, and the other tables are rewritten."""
        file_nodes_before = _file_nodes(compose=infrahub_compose)

        job = json.loads(
            _python_in_task_manager(compose=infrahub_compose, script=_CLEANUP_WITH_SHORT_LOCK_TIMEOUT_SCRIPT)
        )

        file_nodes_after = _file_nodes(compose=infrahub_compose)
        assert (job["rewrite"], job["rewritten"], job["not_rewritten"]) == ("always", True, ["log"])
        assert sorted(file_nodes_before) == sorted(TASK_HISTORY_TABLES)
        assert {table for table in TASK_HISTORY_TABLES if file_nodes_after[table] != file_nodes_before[table]} == {
            "flow_run",
            "flow_run_state",
            "task_run",
            "task_run_state",
            "artifact",
        }
