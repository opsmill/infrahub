from __future__ import annotations

import json
import shutil
import subprocess  # noqa: S404
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub_testcontainers.container import InfrahubDockerCompose

if TYPE_CHECKING:
    from pathlib import Path

# When both of these resolve to "false" in the task-manager container, Prefect's own
# per-worker database migration and block registration become no-ops, so the container runs
# a single serialized, lock-protected initialization instead of every gunicorn worker racing
# to migrate the empty Prefect database on a cold stack. Both must be "false" for that path
# to engage; either one left unset falls back to Prefect's default ("true") and the race
# returns.
SERIALIZED_INIT_FLAGS = (
    "PREFECT_API_DATABASE_MIGRATE_ON_START",
    "PREFECT_API_BLOCKS_REGISTER_ON_START",
)

# Values inherited from the host would mask the defaults produced by the package and make the
# rendered configuration depend on the CI environment rather than on the code under test.
HOST_OVERRIDES_TO_CLEAR = (
    "INFRAHUB_TESTING_TASKMGR_SCALEOUT",
    "INFRAHUB_TESTING_ENTERPRISE",
    "PREFECT_API_DATABASE_MIGRATE_ON_START",
    "PREFECT_API_BLOCKS_REGISTER_ON_START",
    "PREFECT__SERVER_WEBSERVER_ONLY",
)


@dataclass
class TaskManagerConfigCase:
    name: str
    deployment_type: str | None


TASK_MANAGER_CONFIG_CASES = [
    TaskManagerConfigCase(name="single_node", deployment_type=None),
    TaskManagerConfigCase(name="cluster", deployment_type="cluster"),
]


def _render_task_manager_environment(directory: Path, docker_bin: str) -> dict[str, str | None]:
    """Return the effective ``task-manager`` environment as Docker Compose interpolates it.

    Renders the generated compose file and env file exactly as the running stack would merge
    them, so the assertions reflect the values the container actually receives regardless of
    whether they originate from the compose YAML or the generated ``.env``.
    """

    result = subprocess.run(  # noqa: S603
        [
            docker_bin,
            "compose",
            "-f",
            str(directory / "docker-compose.yml"),
            "--env-file",
            str(directory / ".env"),
            "config",
            "--format",
            "json",
            "task-manager",
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=directory,
    )
    rendered = json.loads(result.stdout)
    environment: dict[str, str | None] = rendered["services"]["task-manager"]["environment"]
    return environment


@pytest.mark.parametrize("case", TASK_MANAGER_CONFIG_CASES, ids=lambda case: case.name)
def test_task_manager_multi_worker_cold_start_serializes_init(
    case: TaskManagerConfigCase,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A multi-worker task-manager must disable Prefect's per-worker one-time init.

    With more than one API worker on a cold stack, leaving the migration and block
    registration flags unset lets every gunicorn worker run Prefect's own initialization
    concurrently, which collides and aborts the stack. The generated configuration must set
    both flags to "false" so a single serialized initialization runs instead.
    """

    docker_bin = shutil.which("docker")
    if docker_bin is None:
        pytest.skip("docker CLI is required to render the compose configuration")

    for variable in HOST_OVERRIDES_TO_CLEAR:
        monkeypatch.delenv(variable, raising=False)
    # More than one API worker is what makes the cold-start initialization race reachable.
    monkeypatch.setenv("INFRAHUB_TESTING_TASKMGR_API_WORKERS", "2")
    # The cluster topology declares database resource limits that must parse for "config".
    monkeypatch.setenv("INFRAHUB_TESTING_DB_CPU_LIMIT", "1")
    monkeypatch.setenv("INFRAHUB_TESTING_DB_MEMORY_LIMIT", "1g")

    InfrahubDockerCompose.init(directory=tmp_path, version="local", deployment_type=case.deployment_type)

    environment = _render_task_manager_environment(directory=tmp_path, docker_bin=docker_bin)

    # The profile's requested worker count must survive: clamping it back to 1 would dodge the
    # race but silently invalidate the profile being measured.
    assert environment.get("WEB_CONCURRENCY") == "2"
    for flag in SERIALIZED_INIT_FLAGS:
        assert environment.get(flag) == "false"
    # The serialized path must be reached on the default topology, not by switching the
    # task-manager into webserver-only scaleout mode (which also changes messaging).
    assert environment.get("PREFECT__SERVER_WEBSERVER_ONLY") != "true"
