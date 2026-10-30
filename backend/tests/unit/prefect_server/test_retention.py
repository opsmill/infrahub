from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from prefect.settings import Settings
from prefect.settings.models.server.events import ServerEventsSettings
from prefect.settings.models.server.services import ServerServicesDBVacuumSettings

from infrahub.config import TaskManagerRetentionSettings
from infrahub.prefect_server.retention import (
    PREFECT_EVENT_TYPES,
    apply_prefect_retention_env,
    background_services_notice,
    build_prefect_retention_env,
    deletes_old_events,
    event_types_with_retention_override,
    prefect_retention_already_set,
    prefect_retention_in_effect,
    remove_blank_vacuum_switch,
    task_run_deletion_off_reason,
    turned_off_cleanup_warnings,
    unlisted_prefect_event_types_warning,
)
from tests.helpers.task_manager_retention import (
    EVENT_RETENTION_OVERRIDES,
    EVENTS_RETENTION_PERIOD,
    LEGACY_EVENTS_RETENTION_PERIOD,
    PREFECT_RETENTION_VARIABLES,
    PREFECT_TEST_MODE_VARIABLES,
    VACUUM_ENABLED,
    VACUUM_RETENTION_PERIOD,
    WEBSERVER_ONLY,
)

if TYPE_CHECKING:
    from collections.abc import Collection
    from pathlib import Path

EVERY_RETENTION_VARIABLE = frozenset(
    {VACUUM_ENABLED, VACUUM_RETENTION_PERIOD, EVENTS_RETENTION_PERIOD, EVENT_RETENTION_OVERRIDES}
)

EVENT_TYPES = ("prefect.flow-run.Completed", "prefect.task-run.Running")


@pytest.fixture
def prefect_settings_sources(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Give Prefect an empty working directory, an absent profiles file and no retention variable."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PREFECT_PROFILES_PATH", str(tmp_path / "profiles.toml"))
    for name in (*PREFECT_RETENTION_VARIABLES, *PREFECT_TEST_MODE_VARIABLES):
        monkeypatch.delenv(name, raising=False)
    return tmp_path


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


def test_default_overrides_keep_internal_events_for_two_days() -> None:
    environ: dict[str, str] = {}

    apply_prefect_retention_env(environ=environ, settings=TaskManagerRetentionSettings(), already_set=frozenset())

    assert environ[EVENTS_RETENTION_PERIOD] == "P7D"
    overrides = json.loads(environ[EVENT_RETENTION_OVERRIDES])
    assert overrides == dict.fromkeys(PREFECT_EVENT_TYPES, "P2D")
    assert overrides["prefect.flow-run.heartbeat"] == "P2D"


def test_durations_keep_their_part_below_a_day() -> None:
    settings = TaskManagerRetentionSettings(task_history="P1DT12H", activity_log="P365D", prefect_own_events="P1DT0.5S")

    variables = build_prefect_retention_env(settings=settings, event_types=EVENT_TYPES[:1])

    assert variables[VACUUM_RETENTION_PERIOD] == "P1DT43200S"
    assert variables[EVENTS_RETENTION_PERIOD] == "P365D"
    assert json.loads(variables[EVENT_RETENTION_OVERRIDES]) == {"prefect.flow-run.Completed": "P1DT0.5S"}


@dataclass
class PrefectReadTestCase:
    name: str
    task_history: str
    activity_log: str
    prefect_own_events: str
    event_types: tuple[str, ...]
    expected_vacuum_retention: timedelta
    expected_events_retention: timedelta
    expected_overrides: dict[str, timedelta]


PREFECT_READ_TEST_CASES: list[PrefectReadTestCase] = [
    PrefectReadTestCase(
        name="whole_days",
        task_history="30d",
        activity_log="365d",
        prefect_own_events="7d",
        event_types=EVENT_TYPES,
        expected_vacuum_retention=timedelta(days=30),
        expected_events_retention=timedelta(days=365),
        expected_overrides={
            "prefect.flow-run.Completed": timedelta(days=7),
            "prefect.task-run.Running": timedelta(days=7),
        },
    ),
    PrefectReadTestCase(
        name="part_below_a_day",
        task_history="P1DT12H",
        activity_log="P365D",
        prefect_own_events="P1DT0.5S",
        event_types=EVENT_TYPES,
        expected_vacuum_retention=timedelta(days=1, hours=12),
        expected_events_retention=timedelta(days=365),
        expected_overrides={
            "prefect.flow-run.Completed": timedelta(days=1, milliseconds=500),
            "prefect.task-run.Running": timedelta(days=1, milliseconds=500),
        },
    ),
    PrefectReadTestCase(
        name="no_event_types_replaces_the_heartbeat_default",
        task_history="30d",
        activity_log="30d",
        prefect_own_events="30d",
        event_types=(),
        expected_vacuum_retention=timedelta(days=30),
        expected_events_retention=timedelta(days=30),
        expected_overrides={},
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
    for name, value in build_prefect_retention_env(settings=settings, event_types=test_case.event_types).items():
        monkeypatch.setenv(name, value)

    vacuum = ServerServicesDBVacuumSettings()
    events = ServerEventsSettings()

    assert vacuum.enabled_vacuum_types == {"events", "flow_runs", "orphans"}
    assert vacuum.retention_period == test_case.expected_vacuum_retention
    assert vacuum.event_retention_overrides == test_case.expected_overrides
    assert events.retention_period == test_case.expected_events_retention


def test_apply_sets_every_variable_missing_from_the_environment() -> None:
    """Per-type overrides equal to the activity log retention shorten nothing, so they are written empty."""
    settings = TaskManagerRetentionSettings(task_history="30d", activity_log="7d", prefect_own_events="7d")
    environ = {"PREFECT_API_DATABASE_CONNECTION_URL": "sqlite+aiosqlite:///prefect.db"}

    warnings = apply_prefect_retention_env(environ=environ, settings=settings, already_set=frozenset())

    assert warnings == []
    assert _with_parsed_overrides(environ) == {
        "PREFECT_API_DATABASE_CONNECTION_URL": "sqlite+aiosqlite:///prefect.db",
        VACUUM_ENABLED: "events,flow_runs",
        VACUUM_RETENTION_PERIOD: "P30D",
        EVENTS_RETENTION_PERIOD: "P7D",
        EVENT_RETENTION_OVERRIDES: {},
    }


@dataclass
class WrittenOverridesTestCase:
    name: str
    activity_log: str
    prefect_own_events: str
    already_set: frozenset[str]
    expected_overrides: dict[str, str]


WRITTEN_OVERRIDES_TEST_CASES: list[WrittenOverridesTestCase] = [
    WrittenOverridesTestCase(
        name="own_events_shorter",
        activity_log="7d",
        prefect_own_events="3d",
        already_set=frozenset(),
        expected_overrides=dict.fromkeys(PREFECT_EVENT_TYPES, "P3D"),
    ),
    WrittenOverridesTestCase(
        name="events_retention_preset",
        activity_log="7d",
        prefect_own_events="7d",
        already_set=frozenset({EVENTS_RETENTION_PERIOD}),
        expected_overrides=dict.fromkeys(PREFECT_EVENT_TYPES, "P7D"),
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in WRITTEN_OVERRIDES_TEST_CASES])
def test_overrides_are_written_only_when_they_can_shorten_the_event_retention(
    test_case: WrittenOverridesTestCase,
) -> None:
    """A preset event retention may be longer than prefect_own_events, so the overrides are kept for it."""
    settings = TaskManagerRetentionSettings(
        task_history="30d", activity_log=test_case.activity_log, prefect_own_events=test_case.prefect_own_events
    )
    environ: dict[str, str] = {}

    apply_prefect_retention_env(environ=environ, settings=settings, already_set=test_case.already_set)

    assert json.loads(environ[EVENT_RETENTION_OVERRIDES]) == test_case.expected_overrides


@dataclass
class PresetVariableTestCase:
    name: str
    preset: str
    preset_value: str
    expected_value: object
    expected_overrides: dict[str, str]
    expected_warning: str


PRESET_VARIABLE_TEST_CASES: list[PresetVariableTestCase] = [
    PresetVariableTestCase(
        name="vacuum_retention_period",
        preset=VACUUM_RETENTION_PERIOD,
        preset_value="P90D",
        expected_value="P90D",
        expected_overrides={},
        expected_warning=f"{VACUUM_RETENTION_PERIOD} is set and overrides task_manager.retention.task_history",
    ),
    PresetVariableTestCase(
        name="events_retention_period",
        preset=EVENTS_RETENTION_PERIOD,
        preset_value="P14D",
        expected_value="P14D",
        expected_overrides=dict.fromkeys(PREFECT_EVENT_TYPES, "P7D"),
        expected_warning=f"{EVENTS_RETENTION_PERIOD} is set and overrides task_manager.retention.activity_log",
    ),
    PresetVariableTestCase(
        name="event_retention_overrides",
        preset=EVENT_RETENTION_OVERRIDES,
        preset_value='{"prefect.flow-run.heartbeat": "P1D"}',
        expected_value={"prefect.flow-run.heartbeat": "P1D"},
        expected_overrides={"prefect.flow-run.heartbeat": "P1D"},
        expected_warning=(
            f"{EVENT_RETENTION_OVERRIDES} is set and overrides task_manager.retention.prefect_own_events"
        ),
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in PRESET_VARIABLE_TEST_CASES])
def test_preset_variable_wins_with_a_warning(test_case: PresetVariableTestCase) -> None:
    settings = TaskManagerRetentionSettings(task_history="30d", activity_log="7d", prefect_own_events="7d")
    environ = {test_case.preset: test_case.preset_value}

    warnings = apply_prefect_retention_env(
        environ=environ, settings=settings, already_set=frozenset({test_case.preset})
    )

    assert warnings == [test_case.expected_warning]
    assert _with_parsed_overrides(environ) == {
        VACUUM_ENABLED: "events,flow_runs",
        VACUUM_RETENTION_PERIOD: "P30D",
        EVENTS_RETENTION_PERIOD: "P7D",
        EVENT_RETENTION_OVERRIDES: test_case.expected_overrides,
        test_case.preset: test_case.expected_value,
    }


def test_preset_vacuum_switch_is_kept_without_an_override_warning() -> None:
    """The switch turns cleanups on or off, so the retentions are still derived from the settings."""
    settings = TaskManagerRetentionSettings(task_history="30d", activity_log="7d", prefect_own_events="7d")
    environ = {VACUUM_ENABLED: "[]"}

    warnings = apply_prefect_retention_env(environ=environ, settings=settings, already_set=frozenset({VACUUM_ENABLED}))

    assert warnings == []
    assert _with_parsed_overrides(environ) == {
        VACUUM_ENABLED: "[]",
        VACUUM_RETENTION_PERIOD: "P30D",
        EVENTS_RETENTION_PERIOD: "P7D",
        EVENT_RETENTION_OVERRIDES: {},
    }


def test_setting_preset_outside_the_environment_is_kept_with_a_warning() -> None:
    settings = TaskManagerRetentionSettings(task_history="30d", activity_log="7d", prefect_own_events="7d")
    environ: dict[str, str] = {}

    warnings = apply_prefect_retention_env(
        environ=environ, settings=settings, already_set=frozenset({EVENTS_RETENTION_PERIOD})
    )

    assert warnings == [
        f"{EVENTS_RETENTION_PERIOD} is set in a Prefect settings file or profile and overrides "
        "task_manager.retention.activity_log"
    ]
    assert _with_parsed_overrides(environ) == {
        VACUUM_ENABLED: "events,flow_runs",
        VACUUM_RETENTION_PERIOD: "P30D",
        EVENT_RETENTION_OVERRIDES: dict.fromkeys(PREFECT_EVENT_TYPES, "P7D"),
    }


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

    warnings = apply_prefect_retention_env(
        environ=environ, settings=settings, already_set=frozenset({EVENTS_RETENTION_PERIOD})
    )

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
class BlankVacuumSwitchTestCase:
    name: str
    environ: dict[str, str]
    expected_environ: dict[str, str]


UNRELATED_VARIABLE = {"PREFECT_API_DATABASE_CONNECTION_URL": "sqlite+aiosqlite:///prefect.db"}

BLANK_VACUUM_SWITCH_TEST_CASES: list[BlankVacuumSwitchTestCase] = [
    BlankVacuumSwitchTestCase(
        name="empty",
        environ={**UNRELATED_VARIABLE, VACUUM_ENABLED: ""},
        expected_environ=UNRELATED_VARIABLE,
    ),
    BlankVacuumSwitchTestCase(
        name="blank",
        environ={**UNRELATED_VARIABLE, VACUUM_ENABLED: "  "},
        expected_environ=UNRELATED_VARIABLE,
    ),
    BlankVacuumSwitchTestCase(
        name="lower_case_name_empty",
        environ={**UNRELATED_VARIABLE, "prefect_server_services_db_vacuum_enabled": ""},
        expected_environ=UNRELATED_VARIABLE,
    ),
    BlankVacuumSwitchTestCase(
        name="false_is_kept",
        environ={**UNRELATED_VARIABLE, VACUUM_ENABLED: "false"},
        expected_environ={**UNRELATED_VARIABLE, VACUUM_ENABLED: "false"},
    ),
    BlankVacuumSwitchTestCase(
        name="empty_unrelated_variable_is_kept",
        environ={**UNRELATED_VARIABLE, WEBSERVER_ONLY: ""},
        expected_environ={**UNRELATED_VARIABLE, WEBSERVER_ONLY: ""},
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in BLANK_VACUUM_SWITCH_TEST_CASES])
def test_blank_vacuum_switch_is_removed_under_any_name_prefect_accepts(test_case: BlankVacuumSwitchTestCase) -> None:
    environ = dict(test_case.environ)

    remove_blank_vacuum_switch(environ=environ)

    assert environ == test_case.expected_environ


def test_environment_with_every_variable_preset_is_left_unchanged() -> None:
    settings = TaskManagerRetentionSettings(task_history="30d", activity_log="7d", prefect_own_events="7d")
    environ = {
        VACUUM_ENABLED: "[]",
        VACUUM_RETENTION_PERIOD: "P90D",
        EVENTS_RETENTION_PERIOD: "P14D",
        EVENT_RETENTION_OVERRIDES: '{"prefect.flow-run.heartbeat": "P1D"}',
    }

    warnings = apply_prefect_retention_env(environ=environ, settings=settings, already_set=EVERY_RETENTION_VARIABLE)

    assert warnings == [
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


TASK_RUNS_NOT_DELETED_WARNING = (
    "PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED does not turn on flow_runs, so old task runs are not deleted and "
    "task_manager.retention.task_history is not applied"
)
EVENTS_NOT_DELETED_WARNING = (
    "PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED does not turn on events, so old events are not deleted and "
    "task_manager.retention.activity_log and task_manager.retention.prefect_own_events are not applied"
)


@dataclass
class TurnedOffCleanupTestCase:
    name: str
    vacuum_enabled: str
    expected_warnings: list[str]


TURNED_OFF_CLEANUP_TEST_CASES: list[TurnedOffCleanupTestCase] = [
    TurnedOffCleanupTestCase(name="true", vacuum_enabled="true", expected_warnings=[]),
    TurnedOffCleanupTestCase(name="events_and_flow_runs", vacuum_enabled="events,flow_runs", expected_warnings=[]),
    TurnedOffCleanupTestCase(
        name="events_only", vacuum_enabled="events", expected_warnings=[TASK_RUNS_NOT_DELETED_WARNING]
    ),
    TurnedOffCleanupTestCase(name="false", vacuum_enabled="false", expected_warnings=[TASK_RUNS_NOT_DELETED_WARNING]),
    TurnedOffCleanupTestCase(
        name="flow_runs_only", vacuum_enabled="flow_runs", expected_warnings=[EVENTS_NOT_DELETED_WARNING]
    ),
    TurnedOffCleanupTestCase(
        name="none",
        vacuum_enabled="[]",
        expected_warnings=[TASK_RUNS_NOT_DELETED_WARNING, EVENTS_NOT_DELETED_WARNING],
    ),
    TurnedOffCleanupTestCase(
        name="unknown_type",
        vacuum_enabled="Flow_Runs",
        expected_warnings=[
            "PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED is not valid: Invalid vacuum type(s): ['Flow_Runs']. "
            "Valid values are: ['events', 'flow_runs', 'orphans']"
        ],
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in TURNED_OFF_CLEANUP_TEST_CASES])
def test_turned_off_cleanups_are_warned(monkeypatch: pytest.MonkeyPatch, test_case: TurnedOffCleanupTestCase) -> None:
    """The warnings follow Prefect's own reading of the switch, where false still deletes old events."""
    monkeypatch.setenv(VACUUM_ENABLED, test_case.vacuum_enabled)

    assert turned_off_cleanup_warnings(vacuum=ServerServicesDBVacuumSettings()) == test_case.expected_warnings


@dataclass
class TaskRunDeletionTestCase:
    name: str
    vacuum_enabled: str
    expected_reason: str | None


TASK_RUN_DELETION_TEST_CASES: list[TaskRunDeletionTestCase] = [
    TaskRunDeletionTestCase(name="events_and_flow_runs", vacuum_enabled="events,flow_runs", expected_reason=None),
    TaskRunDeletionTestCase(name="true", vacuum_enabled="true", expected_reason=None),
    TaskRunDeletionTestCase(
        name="events_only",
        vacuum_enabled="events",
        expected_reason="PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED does not turn on flow_runs",
    ),
    TaskRunDeletionTestCase(
        name="false",
        vacuum_enabled="false",
        expected_reason="PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED does not turn on flow_runs",
    ),
    TaskRunDeletionTestCase(
        name="none",
        vacuum_enabled="[]",
        expected_reason="PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED does not turn on flow_runs",
    ),
    TaskRunDeletionTestCase(
        name="unknown_type",
        vacuum_enabled="Flow_Runs",
        expected_reason=(
            "PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED is not valid: Invalid vacuum type(s): ['Flow_Runs']. "
            "Valid values are: ['events', 'flow_runs', 'orphans']"
        ),
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in TASK_RUN_DELETION_TEST_CASES])
def test_old_task_runs_are_deleted_only_when_the_vacuum_switch_turns_on_flow_runs(
    monkeypatch: pytest.MonkeyPatch, test_case: TaskRunDeletionTestCase
) -> None:
    """The reason follows Prefect's own reading of the switch, where true turns on flow_runs and false does not."""
    monkeypatch.setenv(VACUUM_ENABLED, test_case.vacuum_enabled)

    assert task_run_deletion_off_reason(vacuum=ServerServicesDBVacuumSettings()) == test_case.expected_reason


@dataclass
class EventDeletionTestCase:
    name: str
    vacuum_enabled: str
    expected: bool


EVENT_DELETION_TEST_CASES: list[EventDeletionTestCase] = [
    EventDeletionTestCase(name="events_and_flow_runs", vacuum_enabled="events,flow_runs", expected=True),
    EventDeletionTestCase(name="true", vacuum_enabled="true", expected=True),
    EventDeletionTestCase(name="false", vacuum_enabled="false", expected=True),
    EventDeletionTestCase(name="events_only", vacuum_enabled="events", expected=True),
    EventDeletionTestCase(name="flow_runs_only", vacuum_enabled="flow_runs", expected=False),
    EventDeletionTestCase(name="none", vacuum_enabled="[]", expected=False),
    EventDeletionTestCase(name="unknown_type", vacuum_enabled="Flow_Runs", expected=False),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in EVENT_DELETION_TEST_CASES])
def test_old_events_are_deleted_only_when_the_vacuum_switch_turns_on_events(
    monkeypatch: pytest.MonkeyPatch, test_case: EventDeletionTestCase
) -> None:
    """The answer follows Prefect's own reading of the switch, where false still deletes old events."""
    monkeypatch.setenv(VACUUM_ENABLED, test_case.vacuum_enabled)

    assert deletes_old_events(vacuum=ServerServicesDBVacuumSettings()) is test_case.expected


@dataclass
class AlreadySetTestCase:
    name: str
    files: dict[str, str]
    environ: dict[str, str]
    expected: frozenset[str]


ALREADY_SET_TEST_CASES: list[AlreadySetTestCase] = [
    AlreadySetTestCase(name="nothing_set", files={}, environ={}, expected=frozenset()),
    AlreadySetTestCase(
        name="environment",
        files={},
        environ={VACUUM_RETENTION_PERIOD: "P60D"},
        expected=frozenset({VACUUM_RETENTION_PERIOD}),
    ),
    AlreadySetTestCase(
        name="legacy_environment_name",
        files={},
        environ={LEGACY_EVENTS_RETENTION_PERIOD: "P14D"},
        expected=frozenset({EVENTS_RETENTION_PERIOD}),
    ),
    AlreadySetTestCase(
        name="dotenv_file",
        files={".env": f"{VACUUM_ENABLED}=events\n"},
        environ={},
        expected=frozenset({VACUUM_ENABLED}),
    ),
    AlreadySetTestCase(
        name="prefect_toml",
        files={"prefect.toml": '[server.events]\nretention_period = "P90D"\n'},
        environ={},
        expected=frozenset({EVENTS_RETENTION_PERIOD}),
    ),
    AlreadySetTestCase(
        name="pyproject_toml",
        files={"pyproject.toml": "[tool.prefect.server.services.db_vacuum]\nretention_period = 864000\n"},
        environ={},
        expected=frozenset({VACUUM_RETENTION_PERIOD}),
    ),
    AlreadySetTestCase(
        name="profile",
        files={
            "profiles.toml": (
                'active = "infrahub"\n\n[profiles.infrahub]\n'
                f'{EVENT_RETENTION_OVERRIDES} = \'{{"prefect.flow-run.heartbeat": "P1D"}}\'\n'
            )
        },
        environ={},
        expected=frozenset({EVENT_RETENTION_OVERRIDES}),
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in ALREADY_SET_TEST_CASES])
def test_retention_settings_already_set_by_any_prefect_source(
    monkeypatch: pytest.MonkeyPatch, prefect_settings_sources: Path, test_case: AlreadySetTestCase
) -> None:
    for file_name, content in test_case.files.items():
        (prefect_settings_sources / file_name).write_text(content, encoding="utf-8")
    for name, value in test_case.environ.items():
        monkeypatch.setenv(name, value)

    assert prefect_retention_already_set() == test_case.expected


@dataclass
class InEffectTestCase:
    name: str
    environ: dict[str, str]
    expected: dict[str, str]


IN_EFFECT_TEST_CASES: list[InEffectTestCase] = [
    InEffectTestCase(
        name="derived_values",
        environ={
            VACUUM_ENABLED: "events,flow_runs",
            VACUUM_RETENTION_PERIOD: "P30D",
            EVENTS_RETENTION_PERIOD: "P7D",
            EVENT_RETENTION_OVERRIDES: '{"prefect.flow-run.Completed": "P7D", "prefect.task-run.Running": "P7D"}',
        },
        expected={
            VACUUM_ENABLED: "events,flow_runs",
            VACUUM_RETENTION_PERIOD: "P30D",
            EVENTS_RETENTION_PERIOD: "P7D",
            EVENT_RETENTION_OVERRIDES: "P7D for 2 event types",
        },
    ),
    InEffectTestCase(
        name="overrides_counted_per_retention",
        environ={
            VACUUM_ENABLED: "true",
            VACUUM_RETENTION_PERIOD: "P60D",
            EVENTS_RETENTION_PERIOD: "P14D",
            EVENT_RETENTION_OVERRIDES: (
                '{"prefect.flow-run.Completed": "P3D", "prefect.task-run.Running": "P3D", '
                '"prefect.flow-run.heartbeat": "P1D"}'
            ),
        },
        expected={
            VACUUM_ENABLED: "true",
            VACUUM_RETENTION_PERIOD: "P60D",
            EVENTS_RETENTION_PERIOD: "P14D",
            EVENT_RETENTION_OVERRIDES: "P1D for 1 event types, P3D for 2 event types",
        },
    ),
    InEffectTestCase(
        name="values_as_prefect_parses_them",
        environ={
            VACUUM_ENABLED: "[]",
            VACUUM_RETENTION_PERIOD: "7776000",
            EVENTS_RETENTION_PERIOD: "PT36H",
            EVENT_RETENTION_OVERRIDES: "{}",
        },
        expected={
            VACUUM_ENABLED: "[]",
            VACUUM_RETENTION_PERIOD: "P90D",
            EVENTS_RETENTION_PERIOD: "P1DT43200S",
            EVENT_RETENTION_OVERRIDES: "{}",
        },
    ),
    InEffectTestCase(
        name="vacuum_switch_false",
        environ={
            VACUUM_ENABLED: "false",
            VACUUM_RETENTION_PERIOD: "P30D",
            EVENTS_RETENTION_PERIOD: "P7D",
            EVENT_RETENTION_OVERRIDES: "{}",
        },
        expected={
            VACUUM_ENABLED: "false",
            VACUUM_RETENTION_PERIOD: "P30D",
            EVENTS_RETENTION_PERIOD: "P7D",
            EVENT_RETENTION_OVERRIDES: "{}",
        },
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in IN_EFFECT_TEST_CASES])
@pytest.mark.usefixtures("prefect_settings_sources")
def test_retention_in_effect_is_read_from_prefects_parsed_settings(
    monkeypatch: pytest.MonkeyPatch, test_case: InEffectTestCase
) -> None:
    """The values are the ones Prefect parsed, and the per-type overrides are counted per retention."""
    for name, value in test_case.environ.items():
        monkeypatch.setenv(name, value)

    assert prefect_retention_in_effect(settings=Settings()) == test_case.expected


BACKGROUND_SERVICES_NOTICE = (
    "Task manager retention: PREFECT__SERVER_WEBSERVER_ONLY is set, so this process does not run Prefect's "
    "background services, which delete old task runs and events. Start them with "
    "`infrahub tasks background-services`, which applies task_manager.retention. `prefect server services start` "
    "does not read task_manager.retention: unless it sets the same PREFECT_* variables, it deletes no task runs and "
    "keeps events for Prefect's default of 7 days."
)


@dataclass
class BackgroundServicesNoticeTestCase:
    name: str
    environ: dict[str, str]
    expected_notice: str | None


BACKGROUND_SERVICES_NOTICE_TEST_CASES: list[BackgroundServicesNoticeTestCase] = [
    BackgroundServicesNoticeTestCase(name="unset", environ={}, expected_notice=None),
    BackgroundServicesNoticeTestCase(name="empty", environ={WEBSERVER_ONLY: ""}, expected_notice=None),
    BackgroundServicesNoticeTestCase(
        name="true", environ={WEBSERVER_ONLY: "true"}, expected_notice=BACKGROUND_SERVICES_NOTICE
    ),
    BackgroundServicesNoticeTestCase(
        name="false_is_still_set", environ={WEBSERVER_ONLY: "false"}, expected_notice=BACKGROUND_SERVICES_NOTICE
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in BACKGROUND_SERVICES_NOTICE_TEST_CASES])
def test_background_services_notice_follows_prefects_reading_of_the_variable(
    test_case: BackgroundServicesNoticeTestCase,
) -> None:
    """Prefect runs only its web server for any non-empty value of the variable, so the notice follows the same rule."""
    assert background_services_notice(environ=test_case.environ) == test_case.expected_notice


EVENT_PERSISTER_ENABLED = "PREFECT_SERVER_SERVICES_EVENT_PERSISTER_ENABLED"
TWO_OVERRIDES = '{"prefect.flow-run.Completed": "P7D", "prefect.flow-run.heartbeat": "P7D"}'
BOTH_OVERRIDDEN = frozenset({"prefect.flow-run.Completed", "prefect.flow-run.heartbeat"})


def _retention_environ(
    vacuum_enabled: str, overrides: str | None = TWO_OVERRIDES, event_retention: str = "P30D"
) -> dict[str, str]:
    environ = {VACUUM_ENABLED: vacuum_enabled, EVENTS_RETENTION_PERIOD: event_retention}
    if overrides is not None:
        environ[EVENT_RETENTION_OVERRIDES] = overrides
    return environ


@dataclass
class RetentionOverrideTestCase:
    name: str
    environ: dict[str, str]
    expected: frozenset[str]


RETENTION_OVERRIDE_TEST_CASES: list[RetentionOverrideTestCase] = [
    RetentionOverrideTestCase(
        name="events_and_flow_runs",
        environ=_retention_environ(vacuum_enabled="events,flow_runs"),
        expected=BOTH_OVERRIDDEN,
    ),
    RetentionOverrideTestCase(name="true", environ=_retention_environ(vacuum_enabled="true"), expected=BOTH_OVERRIDDEN),
    RetentionOverrideTestCase(
        name="false_still_deletes_events", environ=_retention_environ(vacuum_enabled="false"), expected=BOTH_OVERRIDDEN
    ),
    RetentionOverrideTestCase(
        name="no_override",
        environ=_retention_environ(vacuum_enabled="events,flow_runs", overrides="{}"),
        expected=frozenset(),
    ),
    RetentionOverrideTestCase(
        name="events_off", environ=_retention_environ(vacuum_enabled="flow_runs"), expected=frozenset()
    ),
    RetentionOverrideTestCase(name="no_cleanup", environ=_retention_environ(vacuum_enabled="[]"), expected=frozenset()),
    RetentionOverrideTestCase(
        name="unknown_vacuum_type", environ=_retention_environ(vacuum_enabled="events,Flow_Runs"), expected=frozenset()
    ),
    RetentionOverrideTestCase(
        name="event_persister_off",
        environ={**_retention_environ(vacuum_enabled="events"), EVENT_PERSISTER_ENABLED: "false"},
        expected=frozenset(),
    ),
    RetentionOverrideTestCase(
        name="override_equal_to_event_retention",
        environ=_retention_environ(
            vacuum_enabled="events", overrides='{"prefect.flow-run.Completed": "P7D"}', event_retention="P7D"
        ),
        expected=frozenset(),
    ),
    RetentionOverrideTestCase(
        name="override_longer_than_event_retention",
        environ=_retention_environ(
            vacuum_enabled="events", overrides='{"prefect.flow-run.Completed": "P7D"}', event_retention="P3D"
        ),
        expected=frozenset(),
    ),
    RetentionOverrideTestCase(
        name="prefect_default_heartbeat_override",
        environ=_retention_environ(vacuum_enabled="events", overrides=None, event_retention="P7D"),
        expected=frozenset(),
    ),
    RetentionOverrideTestCase(
        name="one_shorter_override_among_others",
        environ=_retention_environ(
            vacuum_enabled="events",
            overrides='{"prefect.flow-run.heartbeat": "P1D", "prefect.flow-run.Completed": "P7D"}',
            event_retention="P7D",
        ),
        expected=BOTH_OVERRIDDEN,
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in RETENTION_OVERRIDE_TEST_CASES])
@pytest.mark.usefixtures("prefect_settings_sources")
def test_event_types_with_a_retention_override_follow_what_prefect_deletes(
    monkeypatch: pytest.MonkeyPatch, test_case: RetentionOverrideTestCase
) -> None:
    """Prefect deletes events per type only while it deletes events and an override is shorter than the event retention that caps it."""
    monkeypatch.delenv(EVENT_PERSISTER_ENABLED, raising=False)
    for name, value in test_case.environ.items():
        monkeypatch.setenv(name, value)

    assert event_types_with_retention_override(settings=Settings()) == test_case.expected


STORED_EVENT_TYPES = [
    "prefect.flow-run.Completed",
    "prefect.work-pool.new-status",
    "prefect.work-pool.new-status",
    "prefect.automation.new-action",
    "infrahub.node.created",
    "custom.prefect.flow-run.Completed",
]
UNLISTED_WARNING_PREFIX = (
    "Task manager retention: these stored Prefect event types have no per-type retention in "
    "PREFECT_SERVER_SERVICES_DB_VACUUM_EVENT_RETENTION_OVERRIDES, so they are kept for the activity log retention "
)
NOT_OVERRIDDEN_IN_STORED_EVENT_TYPES = "prefect.automation.new-action, prefect.work-pool.new-status"


@dataclass
class UnlistedWarningTestCase:
    name: str
    stored_event_types: list[str]
    overridden: Collection[str]
    event_retention: timedelta
    expected_warning: str | None


UNLISTED_WARNING_TEST_CASES: list[UnlistedWarningTestCase] = [
    UnlistedWarningTestCase(
        name="infrahub_list_as_overrides",
        stored_event_types=STORED_EVENT_TYPES,
        overridden=PREFECT_EVENT_TYPES,
        event_retention=timedelta(days=30),
        expected_warning=f"{UNLISTED_WARNING_PREFIX}(P30D): {NOT_OVERRIDDEN_IN_STORED_EVENT_TYPES}",
    ),
    UnlistedWarningTestCase(
        name="part_below_a_day",
        stored_event_types=STORED_EVENT_TYPES,
        overridden=PREFECT_EVENT_TYPES,
        event_retention=timedelta(days=1, hours=12),
        expected_warning=f"{UNLISTED_WARNING_PREFIX}(P1DT43200S): {NOT_OVERRIDDEN_IN_STORED_EVENT_TYPES}",
    ),
    UnlistedWarningTestCase(
        name="shorter_than_a_day",
        stored_event_types=STORED_EVENT_TYPES,
        overridden=PREFECT_EVENT_TYPES,
        event_retention=timedelta(hours=12),
        expected_warning=f"{UNLISTED_WARNING_PREFIX}(P0DT43200S): {NOT_OVERRIDDEN_IN_STORED_EVENT_TYPES}",
    ),
    UnlistedWarningTestCase(
        name="operator_overrides",
        stored_event_types=["prefect.flow-run.Completed", "prefect.flow-run.heartbeat"],
        overridden=frozenset({"prefect.flow-run.heartbeat"}),
        event_retention=timedelta(days=7),
        expected_warning=f"{UNLISTED_WARNING_PREFIX}(P7D): prefect.flow-run.Completed",
    ),
    UnlistedWarningTestCase(
        name="every_type_overridden",
        stored_event_types=["infrahub.node.created", "prefect.work-pool.new-status"],
        overridden=frozenset({*PREFECT_EVENT_TYPES, "prefect.work-pool.new-status"}),
        event_retention=timedelta(days=30),
        expected_warning=None,
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in UNLISTED_WARNING_TEST_CASES])
def test_the_warning_names_the_stored_prefect_event_types_without_a_per_type_retention(
    test_case: UnlistedWarningTestCase,
) -> None:
    """Only the stored `prefect.` types without an override are named, once each, with the retention in ISO 8601."""
    warning = unlisted_prefect_event_types_warning(
        stored_event_types=test_case.stored_event_types,
        overridden=test_case.overridden,
        event_retention=test_case.event_retention,
    )

    assert warning == test_case.expected_warning
