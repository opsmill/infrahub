from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from prefect.settings import get_current_settings
from typer.testing import CliRunner

from infrahub.cli import app
from infrahub.cli.tasks import run_background_services
from infrahub.prefect_server.retention import (
    EVENT_RETENTION_OVERRIDES,
    EVENTS_RETENTION_PERIOD,
    PREFECT_EVENT_TYPES,
    VACUUM_ENABLED,
    VACUUM_RETENTION_PERIOD,
)
from tests.helpers.task_manager_retention import PREFECT_RETENTION_VARIABLES, unloaded_task_manager_retention

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

APP_LOGGER = "infrahub.prefect_server.app"


@pytest.fixture
def task_manager_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Generator[None, None, None]:
    with unloaded_task_manager_retention(monkeypatch=monkeypatch, config_file=tmp_path / "absent.toml"):
        yield


@dataclass(frozen=True)
class ServicesStart:
    logged: list[str]
    vacuum_types: set[str]
    task_history: timedelta
    activity_log: timedelta
    own_events: set[timedelta]


class RecordingServicesStarter:
    """Record what had been logged and the Prefect settings in effect each time the services are started."""

    def __init__(self, caplog: pytest.LogCaptureFixture) -> None:
        self._caplog = caplog
        self.starts: list[ServicesStart] = []

    def __call__(self) -> None:
        settings = get_current_settings()
        self.starts.append(
            ServicesStart(
                logged=[record.getMessage() for record in self._caplog.records if record.name == APP_LOGGER],
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
def test_the_retention_is_applied_before_the_services_start(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """The services start once, after the retention of the configuration file has been applied and logged."""
    config_file = _config_file(directory=tmp_path, name="infrahub.toml", retention='task_history = "45d"')
    starter = RecordingServicesStarter(caplog=caplog)

    with caplog.at_level(logging.INFO, logger=APP_LOGGER):
        run_background_services(config_file=str(config_file), start_services=starter)

    assert [start.logged for start in starter.starts] == [
        [
            f"Task manager retention: {VACUUM_ENABLED}=events,flow_runs",
            f"Task manager retention: {VACUUM_RETENTION_PERIOD}=P45D",
            f"Task manager retention: {EVENTS_RETENTION_PERIOD}=P7D",
            f"Task manager retention: {EVENT_RETENTION_OVERRIDES}=P7D for {len(PREFECT_EVENT_TYPES)} event types",
        ]
    ]


@pytest.mark.usefixtures("task_manager_environment")
def test_the_services_read_the_retention_derived_from_the_configuration(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Prefect's settings, read once at import, hold the configured retention when the services start."""
    config_file = _config_file(
        directory=tmp_path,
        name="infrahub.toml",
        retention='task_history = "45d"\nactivity_log = "P14D"\nprefect_own_events = "3d"',
    )
    starter = RecordingServicesStarter(caplog=caplog)

    run_background_services(config_file=str(config_file), start_services=starter)

    assert [
        (start.vacuum_types, start.task_history, start.activity_log, start.own_events) for start in starter.starts
    ] == [({"events", "flow_runs", "orphans"}, timedelta(days=45), timedelta(days=14), {timedelta(days=3)})]


@pytest.mark.usefixtures("task_manager_environment")
def test_an_invalid_retention_stops_the_command_before_the_services_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The command exits with the validation error of the configuration file it is given, leaving Prefect unchanged."""
    config_file = _config_file(directory=tmp_path, name="infrahub.toml", retention='task_history = "PT12H"')
    other_config_file = _config_file(directory=tmp_path, name="other.toml", retention='activity_log = "PT1H"')
    monkeypatch.setenv("INFRAHUB_CONFIG", str(other_config_file))

    result = CliRunner().invoke(app, ["tasks", "background-services", str(config_file)])

    assert (result.exit_code, result.stdout) == (
        1,
        "Configuration not valid, found 1 error(s)\n"
        "  task_manager/retention/task_history | Value error, Invalid task manager retention: task_history must be "
        "at least 1 day (value_error)\n",
    )
    assert {name: os.environ.get(name) for name in PREFECT_RETENTION_VARIABLES} == dict.fromkeys(
        PREFECT_RETENTION_VARIABLES
    )
