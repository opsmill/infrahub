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
    build_prefect_retention_env,
)

VACUUM_ENABLED = "PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED"
VACUUM_RETENTION_PERIOD = "PREFECT_SERVER_SERVICES_DB_VACUUM_RETENTION_PERIOD"
EVENTS_RETENTION_PERIOD = "PREFECT_SERVER_EVENTS_RETENTION_PERIOD"
EVENT_RETENTION_OVERRIDES = "PREFECT_SERVER_SERVICES_DB_VACUUM_EVENT_RETENTION_OVERRIDES"

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


def test_own_events_are_capped_to_the_activity_log() -> None:
    settings = TaskManagerRetentionSettings(task_history="30d", activity_log="7d", prefect_own_events="30d")

    variables = build_prefect_retention_env(settings=settings, event_types=EVENT_TYPES)

    assert json.loads(variables[EVENT_RETENTION_OVERRIDES]) == {
        "prefect.flow-run.Completed": "P7D",
        "prefect.task-run.Running": "P7D",
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


def test_apply_warns_when_own_events_are_capped() -> None:
    settings = TaskManagerRetentionSettings(task_history="30d", activity_log="7d", prefect_own_events="30d")
    environ: dict[str, str] = {}

    warnings = apply_prefect_retention_env(environ=environ, settings=settings)

    assert warnings == [
        "task_manager.retention.prefect_own_events P30D is longer than task_manager.retention.activity_log P7D, "
        "Prefect's own events are kept for P7D"
    ]


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


def test_environment_with_every_variable_preset_is_left_unchanged() -> None:
    settings = TaskManagerRetentionSettings(task_history="30d", activity_log="7d", prefect_own_events="30d")
    environ = {
        VACUUM_ENABLED: "[]",
        VACUUM_RETENTION_PERIOD: "P90D",
        EVENTS_RETENTION_PERIOD: "P14D",
        EVENT_RETENTION_OVERRIDES: '{"prefect.flow-run.heartbeat": "P1D"}',
    }

    warnings = apply_prefect_retention_env(environ=environ, settings=settings)

    assert warnings == [
        "task_manager.retention.prefect_own_events P30D is longer than task_manager.retention.activity_log P7D, "
        "Prefect's own events are kept for P7D",
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
