from __future__ import annotations

import json
import logging
import os
import subprocess  # noqa: S404
import sys
import tomllib
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from prefect.settings import get_current_settings

from infrahub import config
from infrahub.prefect_server.app import apply_infrahub_settings_to_prefect, create_infrahub_prefect
from tests.helpers.task_manager_retention import (
    EVENT_RETENTION_OVERRIDES,
    EVENTS_RETENTION_PERIOD,
    LEGACY_EVENTS_RETENTION_PERIOD,
    PREFECT_RETENTION_VARIABLES,
    VACUUM_ENABLED,
    VACUUM_RETENTION_PERIOD,
)

if TYPE_CHECKING:
    from pathlib import Path

APP_LOGGER = "infrahub.prefect_server.app"


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
def test_empty_vacuum_switch_keeps_task_run_deletion(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """An empty switch, as a compose file passes for an unset host variable, is replaced with the derived value."""
    monkeypatch.setenv(VACUUM_ENABLED, "")

    with caplog.at_level(logging.WARNING, logger=APP_LOGGER):
        apply_infrahub_settings_to_prefect()

    assert _app_messages(caplog=caplog, level=logging.WARNING) == []
    assert os.environ[VACUUM_ENABLED] == "events,flow_runs"
    assert get_current_settings().server.services.db_vacuum.enabled_vacuum_types == {"events", "flow_runs", "orphans"}


@pytest.mark.usefixtures("task_manager_environment")
def test_empty_vacuum_switch_gives_way_to_a_prefect_settings_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Prefect reads an empty switch as false, which would replace the file value and turn off task run deletion."""
    (tmp_path / "prefect.toml").write_text('[server.services.db_vacuum]\nenabled = "flow_runs"\n', encoding="utf-8")
    monkeypatch.setenv(VACUUM_ENABLED, "")

    with caplog.at_level(logging.WARNING, logger=APP_LOGGER):
        apply_infrahub_settings_to_prefect()

    assert _app_messages(caplog=caplog, level=logging.WARNING) == [
        "PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED does not turn on events, so old events are not deleted and "
        "task_manager.retention.activity_log and task_manager.retention.prefect_own_events are not applied"
    ]
    assert VACUUM_ENABLED not in os.environ
    assert get_current_settings().server.services.db_vacuum.enabled_vacuum_types == {"flow_runs", "orphans"}


@pytest.mark.usefixtures("task_manager_environment")
def test_preset_vacuum_switch_with_flow_runs_keeps_the_task_history_retention(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A preset vacuum switch only turns cleanups on or off, so task_history still sets how long task runs are kept."""
    monkeypatch.setenv(VACUUM_ENABLED, "true")

    with caplog.at_level(logging.WARNING, logger=APP_LOGGER):
        apply_infrahub_settings_to_prefect()

    assert _app_messages(caplog=caplog, level=logging.WARNING) == []
    assert os.environ[VACUUM_ENABLED] == "true"
    vacuum = get_current_settings().server.services.db_vacuum
    assert vacuum.enabled_vacuum_types == {"events", "flow_runs", "orphans"}
    assert vacuum.retention_period == timedelta(days=30)


@pytest.mark.usefixtures("task_manager_environment")
def test_preset_vacuum_switch_that_turns_off_a_cleanup_is_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv(VACUUM_ENABLED, "flow_runs")

    with caplog.at_level(logging.WARNING, logger=APP_LOGGER):
        apply_infrahub_settings_to_prefect()

    assert _app_messages(caplog=caplog, level=logging.WARNING) == [
        "PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED does not turn on events, so old events are not deleted and "
        "task_manager.retention.activity_log and task_manager.retention.prefect_own_events are not applied"
    ]
    assert get_current_settings().server.services.db_vacuum.enabled_vacuum_types == {"flow_runs", "orphans"}


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


@pytest.mark.usefixtures("task_manager_environment")
def test_a_setting_outside_the_task_manager_section_does_not_stop_the_task_manager(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = tmp_path / "infrahub.toml"
    config_file.write_text(
        '[git]\ndelete_git_branch_after_merge = true\n\n[storage]\ndriver = "nope"\n\n'
        '[task_manager.retention]\ntask_history = "45d"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("INFRAHUB_CONFIG", str(config_file))

    apply_infrahub_settings_to_prefect()

    assert get_current_settings().server.services.db_vacuum.retention_period == timedelta(days=45)
    assert config.SETTINGS.initialized is False


@pytest.mark.usefixtures("task_manager_environment")
def test_an_invalid_retention_in_the_configuration_file_stops_the_task_manager(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_file = tmp_path / "infrahub.toml"
    config_file.write_text(
        '[storage]\ndriver = "nope"\n\n[task_manager.retention]\ntask_history = "PT12H"\n', encoding="utf-8"
    )
    monkeypatch.setenv("INFRAHUB_CONFIG", str(config_file))

    with pytest.raises(SystemExit) as exit_info:
        apply_infrahub_settings_to_prefect()

    assert exit_info.value.code == 1
    assert capsys.readouterr().out == (
        "Configuration not valid, found 1 error(s)\n"
        "  task_manager/retention/task_history | Value error, Invalid task manager retention: task_history must be "
        "at least 1 day (value_error)\n"
    )
    assert {name: os.environ.get(name) for name in PREFECT_RETENTION_VARIABLES} == dict.fromkeys(
        PREFECT_RETENTION_VARIABLES
    )


@pytest.mark.usefixtures("task_manager_environment")
def test_a_configuration_file_that_cannot_be_parsed_stops_the_task_manager(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = tmp_path / "infrahub.toml"
    config_file.write_text("[task_manager.retention\n", encoding="utf-8")
    monkeypatch.setenv("INFRAHUB_CONFIG", str(config_file))

    with pytest.raises(
        tomllib.TOMLDecodeError, match=r"^Expected '\]' at the end of a table declaration \(at line 1, column 24\)$"
    ):
        apply_infrahub_settings_to_prefect()

    assert {name: os.environ.get(name) for name in PREFECT_RETENTION_VARIABLES} == dict.fromkeys(
        PREFECT_RETENTION_VARIABLES
    )


_STANDALONE_TASK_MANAGER_SCRIPT = """
import sys

from prefect.settings import get_current_settings

from infrahub.prefect_server.app import apply_infrahub_settings_to_prefect

apply_infrahub_settings_to_prefect()
retention_period = get_current_settings().server.services.db_vacuum.retention_period
print("infrahub.config" in sys.modules, "infrahub.log" in sys.modules, retention_period.days)
"""


def test_the_standalone_task_manager_ignores_infrahub_settings_it_does_not_use(tmp_path: Path) -> None:
    """A fresh process is needed because this one has already imported Infrahub's configuration."""
    environ = {
        name: value
        for name, value in os.environ.items()
        if name not in PREFECT_RETENTION_VARIABLES
        and not name.startswith(("INFRAHUB_TASK_MANAGER_", "PREFECT_API_BLOCKS_", "PREFECT_API_DATABASE_"))
    }
    environ |= {
        "INFRAHUB_CONFIG": str(tmp_path / "absent.toml"),
        "PREFECT_PROFILES_PATH": str(tmp_path / "profiles.toml"),
        "INFRAHUB_LOG_LEVEL": "INFO",
        "INFRAHUB_PRODUCTION": "true",
        "INFRAHUB_STORAGE_DRIVER": "nope",
        "INFRAHUB_TASK_MANAGER_RETENTION_TASK_HISTORY": "45d",
    }

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _STANDALONE_TASK_MANAGER_SCRIPT],
        cwd=tmp_path,
        env=environ,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )

    assert (result.returncode, result.stdout) == (0, "False True 45\n"), result.stderr
    task_history_log_lines = [
        line["event"]
        for line in (json.loads(text) for text in result.stderr.splitlines() if text.startswith("{"))
        if line.get("logger") == APP_LOGGER and VACUUM_RETENTION_PERIOD in line["event"]
    ]
    assert task_history_log_lines == [f"Task manager retention: {VACUUM_RETENTION_PERIOD}=P45D"]


@pytest.mark.usefixtures("task_manager_environment")
def test_startup_logs_the_retention_prefect_applies(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The startup log shows the value Prefect applies for each retention, derived by Infrahub or preset."""
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
def test_default_retention_writes_no_per_type_override(caplog: pytest.LogCaptureFixture) -> None:
    """With equal own-event and activity log retentions, Prefect's general event cleanup alone applies both."""
    with caplog.at_level(logging.INFO, logger=APP_LOGGER):
        apply_infrahub_settings_to_prefect()

    assert _app_messages(caplog=caplog, level=logging.INFO) == [
        f"Task manager retention: {VACUUM_ENABLED}=events,flow_runs",
        f"Task manager retention: {VACUUM_RETENTION_PERIOD}=P30D",
        f"Task manager retention: {EVENTS_RETENTION_PERIOD}=P7D",
        f"Task manager retention: {EVENT_RETENTION_OVERRIDES}={{}}",
    ]
    assert get_current_settings().server.services.db_vacuum.event_retention_overrides == {}


@pytest.mark.usefixtures("task_manager_environment")
def test_preset_legacy_variable_is_named_in_the_warning_and_its_value_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A retention preset under Prefect's legacy variable name is the one Prefect applies, and the warning names it."""
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
        f"Task manager retention: {EVENTS_RETENTION_PERIOD}=P3D",
        f"Task manager retention: {EVENT_RETENTION_OVERRIDES}=P1D for 1 event types",
    ]
    assert EVENTS_RETENTION_PERIOD not in os.environ
    assert get_current_settings().server.events.retention_period == timedelta(days=3)


@dataclass
class PrefectSettingsFileTestCase:
    name: str
    file_name: str
    content: str


PREFECT_SETTINGS_FILE_TEST_CASES: list[PrefectSettingsFileTestCase] = [
    PrefectSettingsFileTestCase(
        name="prefect_toml", file_name="prefect.toml", content='[server.events]\nretention_period = "P90D"\n'
    ),
    PrefectSettingsFileTestCase(name="dotenv", file_name=".env", content=f"{EVENTS_RETENTION_PERIOD}=P90D\n"),
    PrefectSettingsFileTestCase(
        name="active_profile",
        file_name="profiles.toml",
        content=f'active = "infrahub"\n\n[profiles.infrahub]\n{EVENTS_RETENTION_PERIOD} = "P90D"\n',
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in PREFECT_SETTINGS_FILE_TEST_CASES])
@pytest.mark.usefixtures("task_manager_environment")
def test_retention_set_in_a_prefect_settings_file_is_kept_and_logged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, test_case: PrefectSettingsFileTestCase
) -> None:
    """An environment variable would replace a value Prefect reads from its own files, so none is written for it."""
    (tmp_path / test_case.file_name).write_text(test_case.content, encoding="utf-8")

    with caplog.at_level(logging.INFO, logger=APP_LOGGER):
        apply_infrahub_settings_to_prefect()

    assert _app_messages(caplog=caplog, level=logging.WARNING) == [
        f"{EVENTS_RETENTION_PERIOD} is set in a Prefect settings file or profile and overrides "
        "task_manager.retention.activity_log"
    ]
    assert EVENTS_RETENTION_PERIOD not in os.environ
    assert get_current_settings().server.events.retention_period == timedelta(days=90)
    events_retention_log_lines = [
        message for message in _app_messages(caplog=caplog, level=logging.INFO) if EVENTS_RETENTION_PERIOD in message
    ]
    assert events_retention_log_lines == [f"Task manager retention: {EVENTS_RETENTION_PERIOD}=P90D"]
