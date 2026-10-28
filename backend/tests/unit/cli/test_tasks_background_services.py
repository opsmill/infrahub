from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from prefect.settings import get_current_settings
from typer.testing import CliRunner

from infrahub.cli import app
from infrahub.cli.tasks import run_background_services
from tests.helpers.task_manager_retention import PREFECT_RETENTION_VARIABLES, unloaded_task_manager_retention

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


@pytest.fixture
def task_manager_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Generator[None, None, None]:
    with unloaded_task_manager_retention(monkeypatch=monkeypatch, directory=tmp_path):
        yield


@dataclass(frozen=True)
class ServicesStart:
    vacuum_types: set[str]
    task_history: timedelta
    activity_log: timedelta
    own_events: set[timedelta]


class RecordingServicesStarter:
    """Record the Prefect settings in effect each time the services are started."""

    def __init__(self) -> None:
        self.starts: list[ServicesStart] = []

    def __call__(self) -> None:
        settings = get_current_settings()
        self.starts.append(
            ServicesStart(
                vacuum_types=settings.server.services.db_vacuum.enabled_vacuum_types,
                task_history=settings.server.services.db_vacuum.retention_period,
                activity_log=settings.server.events.retention_period,
                own_events=set(settings.server.services.db_vacuum.event_retention_overrides.values()),
            )
        )


def _config_file(directory: Path, name: str, retention: str) -> Path:
    path = directory / name
    path.write_text(f"[task_manager.retention]\n{retention}\n", encoding="utf-8")
    return path


@pytest.mark.usefixtures("task_manager_environment")
def test_the_services_start_once_with_the_retention_of_the_given_configuration_file(tmp_path: Path) -> None:
    """Prefect's settings hold the retention of the configuration file the command is given when the services start."""
    config_file = _config_file(
        directory=tmp_path,
        name="background-services.toml",
        retention='task_history = "45d"\nactivity_log = "P14D"\nprefect_own_events = "3d"',
    )
    starter = RecordingServicesStarter()

    run_background_services(config_file=config_file, start_services=starter)

    assert starter.starts == [
        ServicesStart(
            vacuum_types={"events", "flow_runs", "orphans"},
            task_history=timedelta(days=45),
            activity_log=timedelta(days=14),
            own_events={timedelta(days=3)},
        )
    ]


@pytest.mark.usefixtures("task_manager_environment")
def test_an_invalid_retention_stops_the_command_before_the_services_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The command exits with the given configuration file's validation error, without starting the services or changing Prefect's settings."""
    config_file = _config_file(directory=tmp_path, name="infrahub.toml", retention='task_history = "PT12H"')
    other_config_file = _config_file(directory=tmp_path, name="other.toml", retention='activity_log = "PT1H"')
    monkeypatch.setenv("INFRAHUB_CONFIG", str(other_config_file))
    starter = RecordingServicesStarter()

    with pytest.raises(SystemExit) as exit_info:
        run_background_services(config_file=config_file, start_services=starter)

    assert (exit_info.value.code, capsys.readouterr().out, starter.starts) == (
        1,
        "Configuration not valid, found 1 error(s)\n"
        "  task_manager/retention/task_history | Value error, Invalid task manager retention: task_history must be "
        "at least 1 day (value_error)\n",
        [],
    )
    assert {name: os.environ.get(name) for name in PREFECT_RETENTION_VARIABLES} == dict.fromkeys(
        PREFECT_RETENTION_VARIABLES
    )


@pytest.mark.usefixtures("task_manager_environment")
def test_a_configuration_file_given_on_the_command_line_must_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mistyped path stops the command, instead of starting the services with the default retention."""
    missing = tmp_path / "infrahub.tml"
    # An invalid retention stops a run that gets past the check before Prefect's services start.
    monkeypatch.setenv("INFRAHUB_TASK_MANAGER_RETENTION_TASK_HISTORY", "PT12H")

    result = CliRunner().invoke(app, ["tasks", "background-services", str(missing)])

    assert (result.exit_code, result.stdout) == (1, f"Configuration file not found: {missing}\n")
    assert {name: os.environ.get(name) for name in PREFECT_RETENTION_VARIABLES} == dict.fromkeys(
        PREFECT_RETENTION_VARIABLES
    )


@pytest.mark.usefixtures("task_manager_environment")
def test_a_missing_configuration_file_leaves_the_retention_to_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deployments that set every value in the environment, such as the test compose files, run the command without a file."""
    monkeypatch.setenv("INFRAHUB_TASK_MANAGER_RETENTION_TASK_HISTORY", "45d")
    starter = RecordingServicesStarter()

    run_background_services(config_file=tmp_path / "absent.toml", start_services=starter)

    assert starter.starts == [
        ServicesStart(
            vacuum_types={"events", "flow_runs", "orphans"},
            task_history=timedelta(days=45),
            activity_log=timedelta(days=7),
            own_events=set(),
        )
    ]
