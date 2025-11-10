from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest
from infrahub_testcontainers.container import InfrahubDockerCompose
from testcontainers.core.exceptions import ContainerIsNotRunning


@pytest.fixture(name="compose_factory")
def fixture_compose_factory(tmp_path: Path) -> Callable[[], InfrahubDockerCompose]:
    """Provide a factory that yields an isolated ``InfrahubDockerCompose`` test double."""

    def _factory() -> InfrahubDockerCompose:
        instance = InfrahubDockerCompose.__new__(InfrahubDockerCompose)
        instance.context = tmp_path
        instance.env_vars = {
            "INFRAHUB_TESTING_LOCAL_DB_BACKUP_DIRECTORY": "backups",
            "INFRAHUB_TESTING_INTERNAL_DB_BACKUP_DIRECTORY": "/backups",
            "NEO4J_DOCKER_IMAGE": "neo4j:2025.03.0-enterprise",
        }
        instance.services = []
        instance.pull = False
        instance.wait = False
        instance.compose_file_name = None
        instance.docker_command_path = None
        instance.project_name = None
        instance.env_file = None

        def _noop_service(service_name: str) -> None:
            """Consume a service name without performing any action."""

            _ = service_name

        instance.get_container = _noop_service  # type: ignore[assignment]
        instance.start_container = _noop_service  # type: ignore[assignment]
        instance.exec_calls: list[list[str]] = []

        def _exec(command: list[str], service_name: str) -> tuple[str, str, int]:
            _ = service_name
            instance.exec_calls.append(command)
            if command and command[0] == "pg_dump":
                file_arg = next(arg for arg in command if arg.startswith("--file="))
                container_path = Path(file_arg.split("=", 1)[1])
                host_path = instance.external_backup_dir / container_path.name
                host_path.parent.mkdir(parents=True, exist_ok=True)
                host_path.write_bytes(b"backup-bytes")
            return "", "", 0

        instance.exec_in_container = _exec  # type: ignore[assignment]
        return instance

    return _factory


def test_task_manager_db_create_backup_creates_archive(compose_factory: Callable[[], InfrahubDockerCompose]) -> None:
    compose = compose_factory()

    result = compose.task_manager_db_create_backup()

    assert result.name == "prefect.dump"
    assert result.exists()
    assert compose.exec_calls[0][0] == "pg_dump"


def test_task_manager_db_create_backup_respects_destination(
    compose_factory: Callable[[], InfrahubDockerCompose], tmp_path: Path
) -> None:
    compose = compose_factory()
    destination = tmp_path / "exports"

    result = compose.task_manager_db_create_backup(dest_dir=destination)

    assert result.parent == destination
    assert result.exists()
    assert (compose.external_backup_dir / "prefect.dump").exists()


def test_task_manager_db_restore_backup_runs_expected_commands(
    compose_factory: Callable[[], InfrahubDockerCompose], tmp_path: Path
) -> None:
    compose = compose_factory()

    def _raise(service_name: str) -> None:
        _ = service_name
        raise ContainerIsNotRunning("task-manager-db")

    compose.get_container = _raise  # type: ignore[assignment]
    started_services: list[str] = []

    def _record_start(service_name: str) -> None:
        started_services.append(service_name)

    compose.start_container = _record_start  # type: ignore[assignment]
    recorded_commands: list[list[str]] = []

    def _exec(command: list[str], service_name: str) -> tuple[str, str, int]:
        _ = service_name
        recorded_commands.append(command)
        return "", "", 0

    compose.exec_in_container = _exec  # type: ignore[assignment]

    backup_file = tmp_path / "prefect.dump"
    backup_file.write_bytes(b"backup")

    compose.task_manager_db_restore_backup(backup_file)

    assert started_services == ["task-manager-db"]
    assert (compose.external_backup_dir / backup_file.name).exists()
    assert [command[0] for command in recorded_commands] == [
        "psql",
        "psql",
        "psql",
        "pg_restore",
    ]
