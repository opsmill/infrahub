from __future__ import annotations

import logging
import os
from datetime import timedelta
from typing import TYPE_CHECKING

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
from tests.helpers.task_manager_retention import (
    LEGACY_EVENTS_RETENTION_PERIOD,
    PREFECT_RETENTION_VARIABLES,
    unloaded_task_manager_retention,
)

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

APP_LOGGER = "infrahub.prefect_server.app"


@pytest.fixture
def task_manager_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Generator[None, None, None]:
    with unloaded_task_manager_retention(monkeypatch=monkeypatch, config_file=tmp_path / "absent.toml"):
        yield


def _app_messages(caplog: pytest.LogCaptureFixture, level: int) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.name == APP_LOGGER and record.levelno == level]


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

    assert _app_messages(caplog=caplog, level=logging.WARNING) == [
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

    assert _app_messages(caplog=caplog, level=logging.WARNING) == [
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


@pytest.mark.usefixtures("task_manager_environment")
def test_startup_logs_the_retention_variables_prefect_reads(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The startup log shows the value of each retention variable, whether Infrahub derived it or it was preset."""
    monkeypatch.setenv("INFRAHUB_TASK_MANAGER_RETENTION_TASK_HISTORY", "45d")
    monkeypatch.setenv("INFRAHUB_TASK_MANAGER_RETENTION_ACTIVITY_LOG", "P14D")
    monkeypatch.setenv(EVENT_RETENTION_OVERRIDES, '{"prefect.flow-run.heartbeat": "P1D"}')

    with caplog.at_level(logging.INFO, logger=APP_LOGGER):
        apply_infrahub_settings_to_prefect()

    assert _app_messages(caplog=caplog, level=logging.INFO) == [
        f"Task manager retention: {VACUUM_ENABLED}=events,flow_runs",
        f"Task manager retention: {VACUUM_RETENTION_PERIOD}=P45D",
        f"Task manager retention: {EVENTS_RETENTION_PERIOD}=P14D",
        f"Task manager retention: {EVENT_RETENTION_OVERRIDES}=P1D for 1 event types",
    ]


@pytest.mark.usefixtures("task_manager_environment")
def test_preset_legacy_variable_is_logged_and_applied_under_its_own_name(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A retention preset under Prefect's legacy variable name is the one Prefect applies, and both logs name it."""
    monkeypatch.setenv(LEGACY_EVENTS_RETENTION_PERIOD, "P3D")
    monkeypatch.setenv(EVENT_RETENTION_OVERRIDES, '{"prefect.flow-run.heartbeat": "P1D"}')

    with caplog.at_level(logging.INFO, logger=APP_LOGGER):
        apply_infrahub_settings_to_prefect()

    assert _app_messages(caplog=caplog, level=logging.WARNING) == [
        f"{LEGACY_EVENTS_RETENTION_PERIOD} is set and overrides task_manager.retention.activity_log",
        f"{EVENT_RETENTION_OVERRIDES} is set and overrides task_manager.retention.prefect_own_events",
    ]
    assert _app_messages(caplog=caplog, level=logging.INFO) == [
        f"Task manager retention: {VACUUM_ENABLED}=events,flow_runs",
        f"Task manager retention: {VACUUM_RETENTION_PERIOD}=P30D",
        f"Task manager retention: {LEGACY_EVENTS_RETENTION_PERIOD}=P3D",
        f"Task manager retention: {EVENT_RETENTION_OVERRIDES}=P1D for 1 event types",
    ]
    assert EVENTS_RETENTION_PERIOD not in os.environ
    assert get_current_settings().server.events.retention_period == timedelta(days=3)
