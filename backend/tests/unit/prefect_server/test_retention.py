from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta

import pytest
from prefect.settings.models.server.events import ServerEventsSettings
from prefect.settings.models.server.services import ServerServicesDBVacuumSettings

from infrahub.config import TaskManagerRetentionSettings
from infrahub.prefect_server.retention import (
    PREFECT_EVENT_TYPES,
    apply_prefect_retention_env,
    background_services_warning,
    build_prefect_retention_env,
    prefect_retention_env_in_effect,
    remove_blank_retention_variables,
)

VACUUM_ENABLED = "PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED"
VACUUM_RETENTION_PERIOD = "PREFECT_SERVER_SERVICES_DB_VACUUM_RETENTION_PERIOD"
EVENTS_RETENTION_PERIOD = "PREFECT_SERVER_EVENTS_RETENTION_PERIOD"
EVENT_RETENTION_OVERRIDES = "PREFECT_SERVER_SERVICES_DB_VACUUM_EVENT_RETENTION_OVERRIDES"
WEBSERVER_ONLY = "PREFECT__SERVER_WEBSERVER_ONLY"

EVENT_TYPES = ("prefect.flow-run.Completed", "prefect.task-run.Running")


def _with_parsed_overrides(environ: dict[str, str]) -> dict[str, object]:
    return {**environ, EVENT_RETENTION_OVERRIDES: json.loads(environ[EVENT_RETENTION_OVERRIDES])}


def test_variables_follow_the_retention() -> None:
    settings = TaskManagerRetentionSettings(task_history="30d", activity_log="7d", prefect_own_events="3d")

    variables = build_prefect_retention_env(settings=settings, event_types=EVENT_TYPES)

    assert _with_parsed_overrides(variables) == {
        VACUUM_ENABLED: "events,flow_runs",
        VACUUM_RETENTION_PERIOD: "P30D",
        EVENTS_RETENTION_PERIOD: "P7D",
        EVENT_RETENTION_OVERRIDES: {"prefect.flow-run.Completed": "P3D", "prefect.task-run.Running": "P3D"},
    }


def test_durations_keep_their_part_below_a_day() -> None:
    settings = TaskManagerRetentionSettings(task_history="P1DT12H", activity_log="P400D", prefect_own_events="P1DT0.5S")

    variables = build_prefect_retention_env(settings=settings, event_types=EVENT_TYPES[:1])

    assert variables[VACUUM_RETENTION_PERIOD] == "P1DT43200S"
    assert variables[EVENTS_RETENTION_PERIOD] == "P400D"
    assert json.loads(variables[EVENT_RETENTION_OVERRIDES]) == {"prefect.flow-run.Completed": "P1DT0.5S"}


@dataclass
class PrefectReadTestCase:
    name: str
    task_history: str
    activity_log: str
    prefect_own_events: str
    expected_vacuum_retention: timedelta
    expected_events_retention: timedelta
    expected_own_events_retention: timedelta


PREFECT_READ_TEST_CASES: list[PrefectReadTestCase] = [
    PrefectReadTestCase(
        name="whole_days",
        task_history="30d",
        activity_log="365d",
        prefect_own_events="7d",
        expected_vacuum_retention=timedelta(days=30),
        expected_events_retention=timedelta(days=365),
        expected_own_events_retention=timedelta(days=7),
    ),
    PrefectReadTestCase(
        name="part_below_a_day",
        task_history="P1DT12H",
        activity_log="P400D",
        prefect_own_events="P1DT0.5S",
        expected_vacuum_retention=timedelta(days=1, hours=12),
        expected_events_retention=timedelta(days=400),
        expected_own_events_retention=timedelta(days=1, milliseconds=500),
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in PREFECT_READ_TEST_CASES])
def test_prefect_reads_the_derived_values(monkeypatch: pytest.MonkeyPatch, test_case: PrefectReadTestCase) -> None:
    """Prefect's own settings models parse every derived variable to the configured retention."""
    settings = TaskManagerRetentionSettings(
        task_history=test_case.task_history,
        activity_log=test_case.activity_log,
        prefect_own_events=test_case.prefect_own_events,
    )
    for name, value in build_prefect_retention_env(settings=settings, event_types=EVENT_TYPES).items():
        monkeypatch.setenv(name, value)

    vacuum = ServerServicesDBVacuumSettings()
    events = ServerEventsSettings()

    assert vacuum.enabled_vacuum_types == {"events", "flow_runs", "orphans"}
    assert vacuum.retention_period == test_case.expected_vacuum_retention
    assert vacuum.event_retention_overrides == {
        "prefect.flow-run.Completed": test_case.expected_own_events_retention,
        "prefect.task-run.Running": test_case.expected_own_events_retention,
    }
    assert events.retention_period == test_case.expected_events_retention


def test_apply_sets_every_variable_missing_from_the_environment() -> None:
    settings = TaskManagerRetentionSettings(task_history="30d", activity_log="7d", prefect_own_events="7d")
    environ = {"PREFECT_API_DATABASE_CONNECTION_URL": "sqlite+aiosqlite:///prefect.db"}

    warnings = apply_prefect_retention_env(environ=environ, settings=settings)

    assert warnings == []
    assert _with_parsed_overrides(environ) == {
        "PREFECT_API_DATABASE_CONNECTION_URL": "sqlite+aiosqlite:///prefect.db",
        VACUUM_ENABLED: "events,flow_runs",
        VACUUM_RETENTION_PERIOD: "P30D",
        EVENTS_RETENTION_PERIOD: "P7D",
        EVENT_RETENTION_OVERRIDES: dict.fromkeys(PREFECT_EVENT_TYPES, "P7D"),
    }


@dataclass
class PresetVariableTestCase:
    name: str
    preset: str
    preset_value: str
    expected_value: object
    expected_warning: str


PRESET_VARIABLE_TEST_CASES: list[PresetVariableTestCase] = [
    PresetVariableTestCase(
        name="vacuum_enabled",
        preset=VACUUM_ENABLED,
        preset_value="[]",
        expected_value="[]",
        expected_warning=f"{VACUUM_ENABLED} is set and overrides task_manager.retention.task_history",
    ),
    PresetVariableTestCase(
        name="vacuum_retention_period",
        preset=VACUUM_RETENTION_PERIOD,
        preset_value="P90D",
        expected_value="P90D",
        expected_warning=f"{VACUUM_RETENTION_PERIOD} is set and overrides task_manager.retention.task_history",
    ),
    PresetVariableTestCase(
        name="events_retention_period",
        preset=EVENTS_RETENTION_PERIOD,
        preset_value="P14D",
        expected_value="P14D",
        expected_warning=f"{EVENTS_RETENTION_PERIOD} is set and overrides task_manager.retention.activity_log",
    ),
    PresetVariableTestCase(
        name="event_retention_overrides",
        preset=EVENT_RETENTION_OVERRIDES,
        preset_value='{"prefect.flow-run.heartbeat": "P1D"}',
        expected_value={"prefect.flow-run.heartbeat": "P1D"},
        expected_warning=(
            f"{EVENT_RETENTION_OVERRIDES} is set and overrides task_manager.retention.prefect_own_events"
        ),
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in PRESET_VARIABLE_TEST_CASES])
def test_preset_variable_wins_with_a_warning(test_case: PresetVariableTestCase) -> None:
    settings = TaskManagerRetentionSettings(task_history="30d", activity_log="7d", prefect_own_events="7d")
    environ = {test_case.preset: test_case.preset_value}

    warnings = apply_prefect_retention_env(environ=environ, settings=settings)

    assert warnings == [test_case.expected_warning]
    assert _with_parsed_overrides(environ) == {
        VACUUM_ENABLED: "events,flow_runs",
        VACUUM_RETENTION_PERIOD: "P30D",
        EVENTS_RETENTION_PERIOD: "P7D",
        EVENT_RETENTION_OVERRIDES: dict.fromkeys(PREFECT_EVENT_TYPES, "P7D"),
        test_case.preset: test_case.expected_value,
    }


LEGACY_EVENTS_RETENTION_PERIOD = "PREFECT_EVENTS_RETENTION_PERIOD"


@dataclass
class AcceptedNameTestCase:
    name: str
    preset: dict[str, str]
    expected_warning: str
    expected_events_retention: timedelta


ACCEPTED_NAME_TEST_CASES: list[AcceptedNameTestCase] = [
    AcceptedNameTestCase(
        name="legacy_name",
        preset={LEGACY_EVENTS_RETENTION_PERIOD: "P14D"},
        expected_warning=f"{LEGACY_EVENTS_RETENTION_PERIOD} is set and overrides task_manager.retention.activity_log",
        expected_events_retention=timedelta(days=14),
    ),
    AcceptedNameTestCase(
        name="lower_case_name",
        preset={"prefect_server_events_retention_period": "P14D"},
        expected_warning=(
            "prefect_server_events_retention_period is set and overrides task_manager.retention.activity_log"
        ),
        expected_events_retention=timedelta(days=14),
    ),
    AcceptedNameTestCase(
        name="current_and_legacy_names",
        preset={EVENTS_RETENTION_PERIOD: "P14D", LEGACY_EVENTS_RETENTION_PERIOD: "P21D"},
        expected_warning=f"{EVENTS_RETENTION_PERIOD} is set and overrides task_manager.retention.activity_log",
        expected_events_retention=timedelta(days=14),
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in ACCEPTED_NAME_TEST_CASES])
def test_setting_preset_under_any_name_prefect_accepts_wins(
    monkeypatch: pytest.MonkeyPatch, test_case: AcceptedNameTestCase
) -> None:
    """A Prefect setting preset under any name Prefect reads is kept, and the warning names the variable found."""
    settings = TaskManagerRetentionSettings(task_history="30d", activity_log="7d", prefect_own_events="7d")
    environ = dict(test_case.preset)

    warnings = apply_prefect_retention_env(environ=environ, settings=settings)

    assert warnings == [test_case.expected_warning]
    assert _with_parsed_overrides(environ) == {
        **test_case.preset,
        VACUUM_ENABLED: "events,flow_runs",
        VACUUM_RETENTION_PERIOD: "P30D",
        EVENT_RETENTION_OVERRIDES: dict.fromkeys(PREFECT_EVENT_TYPES, "P7D"),
    }
    for name in (EVENTS_RETENTION_PERIOD, LEGACY_EVENTS_RETENTION_PERIOD):
        monkeypatch.delenv(name, raising=False)
    for name, value in environ.items():
        monkeypatch.setenv(name, value)
    assert ServerEventsSettings().retention_period == test_case.expected_events_retention


@dataclass
class BlankVariableTestCase:
    name: str
    environ: dict[str, str]
    expected_environ: dict[str, str]


UNRELATED_VARIABLE = {"PREFECT_API_DATABASE_CONNECTION_URL": "sqlite+aiosqlite:///prefect.db"}

BLANK_VARIABLE_TEST_CASES: list[BlankVariableTestCase] = [
    BlankVariableTestCase(
        name="vacuum_enabled_empty",
        environ={**UNRELATED_VARIABLE, VACUUM_ENABLED: ""},
        expected_environ=UNRELATED_VARIABLE,
    ),
    BlankVariableTestCase(
        name="vacuum_enabled_blank",
        environ={**UNRELATED_VARIABLE, VACUUM_ENABLED: "  "},
        expected_environ=UNRELATED_VARIABLE,
    ),
    BlankVariableTestCase(
        name="lower_case_vacuum_enabled_empty",
        environ={**UNRELATED_VARIABLE, "prefect_server_services_db_vacuum_enabled": ""},
        expected_environ=UNRELATED_VARIABLE,
    ),
    BlankVariableTestCase(
        name="vacuum_retention_period_empty",
        environ={**UNRELATED_VARIABLE, VACUUM_RETENTION_PERIOD: ""},
        expected_environ=UNRELATED_VARIABLE,
    ),
    BlankVariableTestCase(
        name="events_retention_period_empty",
        environ={**UNRELATED_VARIABLE, EVENTS_RETENTION_PERIOD: ""},
        expected_environ=UNRELATED_VARIABLE,
    ),
    BlankVariableTestCase(
        name="legacy_events_retention_period_empty",
        environ={**UNRELATED_VARIABLE, LEGACY_EVENTS_RETENTION_PERIOD: ""},
        expected_environ=UNRELATED_VARIABLE,
    ),
    BlankVariableTestCase(
        name="event_retention_overrides_empty",
        environ={**UNRELATED_VARIABLE, EVENT_RETENTION_OVERRIDES: ""},
        expected_environ=UNRELATED_VARIABLE,
    ),
    BlankVariableTestCase(
        name="empty_legacy_name_beside_a_value",
        environ={**UNRELATED_VARIABLE, EVENTS_RETENTION_PERIOD: "P14D", LEGACY_EVENTS_RETENTION_PERIOD: ""},
        expected_environ={**UNRELATED_VARIABLE, EVENTS_RETENTION_PERIOD: "P14D"},
    ),
    BlankVariableTestCase(
        name="false_is_kept",
        environ={**UNRELATED_VARIABLE, VACUUM_ENABLED: "false"},
        expected_environ={**UNRELATED_VARIABLE, VACUUM_ENABLED: "false"},
    ),
    BlankVariableTestCase(
        name="empty_unrelated_variable_is_kept",
        environ={**UNRELATED_VARIABLE, WEBSERVER_ONLY: ""},
        expected_environ={**UNRELATED_VARIABLE, WEBSERVER_ONLY: ""},
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in BLANK_VARIABLE_TEST_CASES])
def test_blank_retention_variable_is_removed_under_any_name_prefect_accepts(test_case: BlankVariableTestCase) -> None:
    environ = dict(test_case.environ)

    remove_blank_retention_variables(environ=environ)

    assert environ == test_case.expected_environ


def test_environment_with_every_variable_preset_is_left_unchanged() -> None:
    settings = TaskManagerRetentionSettings(task_history="30d", activity_log="7d", prefect_own_events="7d")
    environ = {
        VACUUM_ENABLED: "[]",
        VACUUM_RETENTION_PERIOD: "P90D",
        EVENTS_RETENTION_PERIOD: "P14D",
        EVENT_RETENTION_OVERRIDES: '{"prefect.flow-run.heartbeat": "P1D"}',
    }

    warnings = apply_prefect_retention_env(environ=environ, settings=settings)

    assert warnings == [
        f"{VACUUM_ENABLED} is set and overrides task_manager.retention.task_history",
        f"{VACUUM_RETENTION_PERIOD} is set and overrides task_manager.retention.task_history",
        f"{EVENTS_RETENTION_PERIOD} is set and overrides task_manager.retention.activity_log",
        f"{EVENT_RETENTION_OVERRIDES} is set and overrides task_manager.retention.prefect_own_events",
    ]
    assert environ == {
        VACUUM_ENABLED: "[]",
        VACUUM_RETENTION_PERIOD: "P90D",
        EVENTS_RETENTION_PERIOD: "P14D",
        EVENT_RETENTION_OVERRIDES: '{"prefect.flow-run.heartbeat": "P1D"}',
    }


def test_overrides_in_effect_are_counted_per_retention() -> None:
    """The per-type overrides are reported as a count per retention instead of the full list."""
    environ = {
        EVENT_RETENTION_OVERRIDES: json.dumps(
            {
                "prefect.flow-run.Completed": "P3D",
                "prefect.task-run.Running": "P3D",
                "prefect.flow-run.heartbeat": "P1D",
            }
        )
    }

    assert prefect_retention_env_in_effect(environ=environ) == {
        EVENT_RETENTION_OVERRIDES: "P1D for 1 event types, P3D for 2 event types"
    }


def test_overrides_in_effect_that_are_not_a_mapping_are_reported_as_set() -> None:
    environ = {EVENT_RETENTION_OVERRIDES: "not json"}

    assert prefect_retention_env_in_effect(environ=environ) == {EVENT_RETENTION_OVERRIDES: "not json"}


BACKGROUND_SERVICES_WARNING = (
    "Task manager retention: PREFECT__SERVER_WEBSERVER_ONLY is set, so this process does not run Prefect's "
    "background services, which delete old task runs and events. The process that runs them, such as "
    "`prefect server services start`, does not read task_manager.retention: unless it sets the same PREFECT_* "
    "variables, it deletes no task runs and keeps events for Prefect's default of 7 days."
)


@dataclass
class BackgroundServicesWarningTestCase:
    name: str
    environ: dict[str, str]
    expected_warning: str | None


BACKGROUND_SERVICES_WARNING_TEST_CASES: list[BackgroundServicesWarningTestCase] = [
    BackgroundServicesWarningTestCase(name="unset", environ={}, expected_warning=None),
    BackgroundServicesWarningTestCase(name="empty", environ={WEBSERVER_ONLY: ""}, expected_warning=None),
    BackgroundServicesWarningTestCase(
        name="true", environ={WEBSERVER_ONLY: "true"}, expected_warning=BACKGROUND_SERVICES_WARNING
    ),
    BackgroundServicesWarningTestCase(
        name="false_is_still_set", environ={WEBSERVER_ONLY: "false"}, expected_warning=BACKGROUND_SERVICES_WARNING
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in BACKGROUND_SERVICES_WARNING_TEST_CASES])
def test_background_services_warning_follows_prefects_reading_of_the_variable(
    test_case: BackgroundServicesWarningTestCase,
) -> None:
    """Prefect runs only its web server for any non-empty value of the variable, so the warning follows the same rule."""
    assert background_services_warning(environ=test_case.environ) == test_case.expected_warning
