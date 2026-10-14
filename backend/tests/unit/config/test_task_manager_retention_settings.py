from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import pytest
from pydantic import ValidationError

from infrahub.config import TaskManagerRetentionSettings, load

if TYPE_CHECKING:
    from pathlib import Path

RETENTION_ENV_VARIABLES = (
    "INFRAHUB_TASK_MANAGER_RETENTION_TASK_HISTORY",
    "INFRAHUB_TASK_MANAGER_RETENTION_ACTIVITY_LOG",
    "INFRAHUB_TASK_MANAGER_RETENTION_PREFECT_OWN_EVENTS",
)


@pytest.fixture(autouse=True)
def retention_env_cleared(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in RETENTION_ENV_VARIABLES:
        monkeypatch.delenv(name, raising=False)


def test_shipped_defaults() -> None:
    settings = TaskManagerRetentionSettings()

    assert settings.task_history == timedelta(days=30)
    assert settings.activity_log == timedelta(days=7)
    assert settings.prefect_own_events == timedelta(days=7)


@dataclass
class AcceptedRetentionTestCase:
    name: str
    value: str
    expected: timedelta


ACCEPTED_RETENTION_TEST_CASES: list[AcceptedRetentionTestCase] = [
    AcceptedRetentionTestCase(name="days", value="30d", expected=timedelta(days=30)),
    AcceptedRetentionTestCase(name="iso_8601_days", value="P30D", expected=timedelta(days=30)),
    AcceptedRetentionTestCase(name="iso_8601_weeks", value="P2W", expected=timedelta(days=14)),
    AcceptedRetentionTestCase(name="iso_8601_days_and_hours", value="P1DT12H", expected=timedelta(days=1, hours=12)),
    AcceptedRetentionTestCase(name="one_day_is_the_minimum", value="1d", expected=timedelta(days=1)),
    AcceptedRetentionTestCase(name="iso_8601_one_day_is_the_minimum", value="P1D", expected=timedelta(days=1)),
    AcceptedRetentionTestCase(name="surrounding_whitespace", value=" 365d ", expected=timedelta(days=365)),
    AcceptedRetentionTestCase(name="36500_days_is_the_maximum", value="36500d", expected=timedelta(days=36500)),
    AcceptedRetentionTestCase(
        name="iso_8601_36500_days_is_the_maximum", value="P36500D", expected=timedelta(days=36500)
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in ACCEPTED_RETENTION_TEST_CASES])
@pytest.mark.parametrize("key", ["task_history", "activity_log", "prefect_own_events"])
def test_retention_accepts_days_and_iso_8601_durations(key: str, test_case: AcceptedRetentionTestCase) -> None:
    settings = TaskManagerRetentionSettings.model_validate({key: test_case.value})

    assert getattr(settings, key) == test_case.expected


@dataclass
class RefusedRetentionTestCase:
    name: str
    value: Any
    reason: str


SHORTER_THAN_ONE_DAY = "must be at least 1 day"
LONGER_THAN_36500_DAYS = "must be at most 36500 days"
NOT_A_DURATION = "must be a number of days such as 30d or an ISO 8601 duration such as P30D"

REFUSED_RETENTION_TEST_CASES: list[RefusedRetentionTestCase] = [
    RefusedRetentionTestCase(name="zero_days", value="0d", reason=SHORTER_THAN_ONE_DAY),
    RefusedRetentionTestCase(name="iso_8601_under_a_day", value="PT23H59M", reason=SHORTER_THAN_ONE_DAY),
    RefusedRetentionTestCase(name="iso_8601_zero", value="P0D", reason=SHORTER_THAN_ONE_DAY),
    RefusedRetentionTestCase(name="bare_number", value="30", reason=NOT_A_DURATION),
    RefusedRetentionTestCase(name="integer", value=30, reason=NOT_A_DURATION),
    RefusedRetentionTestCase(name="hours_suffix", value="36h", reason=NOT_A_DURATION),
    RefusedRetentionTestCase(name="negative_iso_8601", value="-P30D", reason=NOT_A_DURATION),
    RefusedRetentionTestCase(name="malformed_iso_8601", value="P30X", reason=NOT_A_DURATION),
    RefusedRetentionTestCase(name="python_timedelta_text", value="30 days, 0:00:00", reason=NOT_A_DURATION),
    RefusedRetentionTestCase(name="one_day_over_the_maximum", value="36501d", reason=LONGER_THAN_36500_DAYS),
    RefusedRetentionTestCase(
        name="iso_8601_one_second_over_the_maximum", value="P36500DT1S", reason=LONGER_THAN_36500_DAYS
    ),
    RefusedRetentionTestCase(name="days_beyond_prefect_cutoff", value="800000d", reason=LONGER_THAN_36500_DAYS),
    RefusedRetentionTestCase(name="days_beyond_a_timedelta", value="1000000000d", reason=LONGER_THAN_36500_DAYS),
    RefusedRetentionTestCase(
        name="days_beyond_integer_conversion", value=f"{'9' * 5000}d", reason=LONGER_THAN_36500_DAYS
    ),
    RefusedRetentionTestCase(name="iso_8601_beyond_a_timedelta", value="P1000000000D", reason=LONGER_THAN_36500_DAYS),
    RefusedRetentionTestCase(
        name="iso_8601_with_a_number_too_large", value="PT99999999999999H", reason=LONGER_THAN_36500_DAYS
    ),
    RefusedRetentionTestCase(name="iso_8601_malformed", value="P1X", reason=NOT_A_DURATION),
    RefusedRetentionTestCase(name="iso_8601_without_any_part", value="P", reason=NOT_A_DURATION),
    RefusedRetentionTestCase(name="iso_8601_with_an_empty_time_part", value="PT", reason=NOT_A_DURATION),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in REFUSED_RETENTION_TEST_CASES])
@pytest.mark.parametrize("key", ["task_history", "activity_log", "prefect_own_events"])
def test_retention_refusal_names_the_setting(key: str, test_case: RefusedRetentionTestCase) -> None:
    with pytest.raises(ValidationError, match=re.escape(f"Invalid task manager retention: {key} {test_case.reason}")):
        TaskManagerRetentionSettings.model_validate({key: test_case.value})


def test_own_events_longer_than_activity_log_is_accepted() -> None:
    settings = TaskManagerRetentionSettings(activity_log="7d", prefect_own_events="30d")

    assert settings.activity_log == timedelta(days=7)
    assert settings.prefect_own_events == timedelta(days=30)


def test_environment_variables_set_the_retention(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("INFRAHUB_TASK_MANAGER_RETENTION_TASK_HISTORY", "60d")
    monkeypatch.setenv("INFRAHUB_TASK_MANAGER_RETENTION_ACTIVITY_LOG", "P365D")
    monkeypatch.setenv("INFRAHUB_TASK_MANAGER_RETENTION_PREFECT_OWN_EVENTS", "3d")

    settings = load(config_file_name=tmp_path / "absent.toml")

    assert settings.task_manager.retention.task_history == timedelta(days=60)
    assert settings.task_manager.retention.activity_log == timedelta(days=365)
    assert settings.task_manager.retention.prefect_own_events == timedelta(days=3)


def test_configuration_file_sets_the_retention(tmp_path: Path) -> None:
    config_file = tmp_path / "infrahub.toml"
    config_file.write_text(
        '[task_manager.retention]\ntask_history = "90d"\nactivity_log = "30d"\nprefect_own_events = "P2D"\n',
        encoding="utf-8",
    )

    settings = load(config_file_name=config_file)

    assert settings.task_manager.retention.task_history == timedelta(days=90)
    assert settings.task_manager.retention.activity_log == timedelta(days=30)
    assert settings.task_manager.retention.prefect_own_events == timedelta(days=2)


def test_invalid_environment_variable_fails_the_configuration_load(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("INFRAHUB_TASK_MANAGER_RETENTION_ACTIVITY_LOG", "PT12H")

    with pytest.raises(
        ValidationError, match=re.escape("Invalid task manager retention: activity_log must be at least 1 day")
    ):
        load(config_file_name=tmp_path / "absent.toml")
