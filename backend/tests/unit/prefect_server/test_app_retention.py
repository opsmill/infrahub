from __future__ import annotations

import logging
import os
from datetime import timedelta
from typing import TYPE_CHECKING

import prefect.context
import pytest
from prefect.settings import get_current_settings

from infrahub import config
from infrahub.prefect_server.app import apply_infrahub_settings_to_prefect, create_infrahub_prefect
from infrahub.prefect_server.retention import (
    EVENT_RETENTION_OVERRIDES,
    EVENTS_RETENTION_PERIOD,
    VACUUM_ENABLED,
    VACUUM_RETENTION_PERIOD,
)

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

APP_LOGGER = "infrahub.prefect_server.app"
PREFECT_RETENTION_VARIABLES = (
    VACUUM_ENABLED,
    VACUUM_RETENTION_PERIOD,
    EVENTS_RETENTION_PERIOD,
    EVENT_RETENTION_OVERRIDES,
)


@pytest.fixture
def task_manager_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Generator[None, None, None]:
    """Start from an unloaded configuration and no retention variable, and put the process state back afterwards."""
    monkeypatch.setattr(config.SETTINGS, "settings", None)
    monkeypatch.setattr(prefect.context, "GLOBAL_SETTINGS_CONTEXT", prefect.context.GLOBAL_SETTINGS_CONTEXT)
    monkeypatch.setenv("INFRAHUB_CONFIG", str(tmp_path / "absent.toml"))
    for name in (
        "INFRAHUB_TASK_MANAGER_RETENTION_TASK_HISTORY",
        "INFRAHUB_TASK_MANAGER_RETENTION_ACTIVITY_LOG",
        "INFRAHUB_TASK_MANAGER_RETENTION_PREFECT_OWN_EVENTS",
        "PREFECT_API_BLOCKS_REGISTER_ON_START",
        "PREFECT_API_DATABASE_MIGRATE_ON_START",
    ):
        monkeypatch.delenv(name, raising=False)
    saved = {name: os.environ.pop(name, None) for name in PREFECT_RETENTION_VARIABLES}

    yield

    for name, value in saved.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def _app_warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.name == APP_LOGGER]


@pytest.mark.usefixtures("task_manager_environment")
def test_task_manager_refuses_to_start_on_a_retention_under_one_day(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("INFRAHUB_TASK_MANAGER_RETENTION_TASK_HISTORY", "PT12H")

    with pytest.raises(SystemExit) as exit_info:
        create_infrahub_prefect()

    assert exit_info.value.code == 1
    assert capsys.readouterr().out == (
        "Configuration not valid, found 1 error(s)\n"
        "  task_history | Value error, Invalid task manager retention: task_history must be at least 1 day "
        "(value_error)\n"
    )
    assert {name: os.environ.get(name) for name in PREFECT_RETENTION_VARIABLES} == dict.fromkeys(
        PREFECT_RETENTION_VARIABLES
    )


@pytest.mark.usefixtures("task_manager_environment")
def test_capped_own_events_are_logged(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setenv("INFRAHUB_TASK_MANAGER_RETENTION_ACTIVITY_LOG", "7d")
    monkeypatch.setenv("INFRAHUB_TASK_MANAGER_RETENTION_PREFECT_OWN_EVENTS", "30d")

    with caplog.at_level(logging.WARNING, logger=APP_LOGGER):
        apply_infrahub_settings_to_prefect()

    assert _app_warnings(caplog) == [
        "task_manager.retention.prefect_own_events P30D is longer than task_manager.retention.activity_log P7D, "
        "Prefect's own events are kept for P7D"
    ]


@pytest.mark.usefixtures("task_manager_environment")
def test_each_preset_prefect_variable_is_logged_and_kept(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv(VACUUM_RETENTION_PERIOD, "P2D")
    monkeypatch.setenv(EVENTS_RETENTION_PERIOD, "P3D")

    with caplog.at_level(logging.WARNING, logger=APP_LOGGER):
        apply_infrahub_settings_to_prefect()

    assert _app_warnings(caplog) == [
        f"{VACUUM_RETENTION_PERIOD} is set and overrides task_manager.retention.task_history",
        f"{EVENTS_RETENTION_PERIOD} is set and overrides task_manager.retention.activity_log",
    ]
    prefect_settings = get_current_settings()
    assert prefect_settings.server.services.db_vacuum.retention_period == timedelta(days=2)
    assert prefect_settings.server.events.retention_period == timedelta(days=3)


@pytest.mark.usefixtures("task_manager_environment")
def test_prefect_runs_with_the_configured_retention(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prefect's settings, read once at import, reflect the retention once the configuration is applied."""
    monkeypatch.setenv("INFRAHUB_TASK_MANAGER_RETENTION_TASK_HISTORY", "45d")
    monkeypatch.setenv("INFRAHUB_TASK_MANAGER_RETENTION_ACTIVITY_LOG", "P14D")

    apply_infrahub_settings_to_prefect()

    prefect_settings = get_current_settings()
    assert prefect_settings.server.services.db_vacuum.enabled_vacuum_types == {"events", "flow_runs", "orphans"}
    assert prefect_settings.server.services.db_vacuum.retention_period == timedelta(days=45)
    assert prefect_settings.server.events.retention_period == timedelta(days=14)
    assert config.SETTINGS.task_manager.retention.task_history == timedelta(days=45)
