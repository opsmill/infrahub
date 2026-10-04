from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.testing.docker import TestInfrahubDockerClient

if TYPE_CHECKING:
    from infrahub_testcontainers.container import InfrahubDockerCompose

pytestmark = pytest.mark.shard_a

OLD_RUNS = 300
SCENARIO_DELETED_RUNS = 8

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

_SIZE_QUERY = (
    "SELECT sum(pg_total_relation_size(name::regclass)) FROM unnest(ARRAY"
    "['flow_run', 'flow_run_state', 'task_run', 'task_run_state', 'log', 'artifact']) AS name"
)

_DELETED_RUNS = re.compile(r"Deleted (?P<count>\d+) runs that ended before \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC")


def _python_in_task_manager(compose: InfrahubDockerCompose, script: str) -> str:
    stdout, _, _ = compose.exec_in_container(command=["python", "-c", script], service_name="task-manager")
    return stdout.strip().splitlines()[-1]


def _task_history_size(compose: InfrahubDockerCompose) -> int:
    stdout, _, _ = compose.exec_in_container(
        command=["psql", "--username=postgres", "--dbname=prefect", "--tuples-only", "--no-align", "-c", _SIZE_QUERY],
        service_name="task-manager-db",
    )
    return int(stdout.strip())


def _ids_by_table(ids: dict[str, list[str]]) -> dict[str, set[str]]:
    return {table: set(values) for table, values in ids.items()}


class TestTaskHistoryCleanup(TestInfrahubDockerClient):
    def test_flush_flow_runs_with_rewrite_deletes_the_old_task_history_and_shrinks_its_tables(
        self,
        infrahub_app: dict[str, int],
        infrahub_compose: InfrahubDockerCompose,
    ) -> None:
        """On Postgres the command deletes old finished runs with their children, keeps the rest, and shrinks the tables."""
        seeded = json.loads(_python_in_task_manager(compose=infrahub_compose, script=_SEED_SCRIPT))
        kept, deleted = _ids_by_table(ids=seeded["kept"]), _ids_by_table(ids=seeded["deleted"])
        size_before = _task_history_size(compose=infrahub_compose)

        stdout, _, _ = infrahub_compose.exec_in_container(
            command=["infrahub", "tasks", "flush", "flow-runs", "--rewrite"], service_name="infrahub-server"
        )

        remaining = _ids_by_table(
            ids=json.loads(_python_in_task_manager(compose=infrahub_compose, script=_READ_SCRIPT))
        )
        assert {table: remaining[table] & (kept[table] | deleted[table]) for table in kept} == kept
        assert len(deleted["flow_runs"]) == OLD_RUNS + SCENARIO_DELETED_RUNS
        assert [int(match["count"]) for match in _DELETED_RUNS.finditer(stdout)] == [OLD_RUNS + SCENARIO_DELETED_RUNS]
        assert stdout.strip().splitlines()[-1].strip().endswith("Task history tables rewritten")
        assert _task_history_size(compose=infrahub_compose) < size_before
