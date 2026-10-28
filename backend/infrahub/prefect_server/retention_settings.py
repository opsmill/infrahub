from __future__ import annotations

import re
import tomllib
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from pathlib import Path

_RETENTION_IN_DAYS = re.compile(r"(\d+)d")
_ISO_8601_DURATION = re.compile(
    r"P(?=\d|T\d)(?:\d+Y)?(?:\d+M)?(?:\d+W)?(?:\d+D)?(?:T(?=\d)(?:\d+H)?(?:\d+M)?(?:\d+(?:\.\d+)?S)?)?"
)
_MINIMUM_RETENTION = timedelta(days=1)
# Prefect's cutoff of now minus the retention must stay a valid date, which a century keeps far from overflowing.
_MAXIMUM_RETENTION = timedelta(days=36500)
_TIMEDELTA_ADAPTER: TypeAdapter[timedelta] = TypeAdapter(timedelta)


def _days(count: str) -> timedelta:
    try:
        return timedelta(days=int(count))
    except (OverflowError, ValueError):
        # Still a number of days, so it is refused by the upper bound rather than as an unreadable value.
        return timedelta.max


def _parse_retention(value: Any) -> timedelta | None:
    if isinstance(value, timedelta):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if match := _RETENTION_IN_DAYS.fullmatch(text):
        return _days(count=match.group(1))
    # Pydantic also reads forms such as "1 day, 00:00:00", which are not part of the documented contract.
    if not text.startswith("P"):
        return None
    try:
        return _TIMEDELTA_ADAPTER.validate_python(text)
    except ValidationError:
        # A well-formed duration too large to read is refused by the upper bound rather than as an unreadable value.
        return timedelta.max if _ISO_8601_DURATION.fullmatch(text) else None


class TaskManagerRetentionSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFRAHUB_TASK_MANAGER_RETENTION_")

    task_history: timedelta = Field(
        default="30d",
        validate_default=True,
        description=(
            "How long finished task runs are kept, with their logs and artifacts, as a number of days (`30d`) "
            "or an ISO 8601 duration (`P30D`), from 1 to 36500 days. "
            "`PREFECT_SERVER_SERVICES_DB_VACUUM_RETENTION_PERIOD` takes precedence when set. When "
            "`PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED` is set to a value that does not turn on `flow_runs`, old "
            "task runs are not deleted."
        ),
    )
    activity_log: timedelta = Field(
        default="7d",
        validate_default=True,
        description=(
            "How long the events of the activity log are kept, as a number of days (`7d`) or an ISO 8601 "
            "duration (`P7D`), from 1 to 36500 days, and at least `prefect_own_events`. "
            "`PREFECT_SERVER_EVENTS_RETENTION_PERIOD`, or its legacy name `PREFECT_EVENTS_RETENTION_PERIOD`, takes "
            "precedence when set. When `PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED` is set to a value that does not "
            "turn on `events`, old events are not deleted."
        ),
    )
    prefect_own_events: timedelta = Field(
        default="7d",
        validate_default=True,
        description=(
            "How long the task manager's own Prefect events are kept, as a number of days (`7d`) or an ISO 8601 "
            "duration (`P7D`), from 1 to 36500 days, and at most `activity_log`. "
            "`PREFECT_SERVER_SERVICES_DB_VACUUM_EVENT_RETENTION_OVERRIDES` takes precedence when set. When "
            "`PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED` is set to a value that does not turn on `events`, old "
            "events are not deleted."
        ),
    )

    @field_validator("task_history", "activity_log", "prefect_own_events", mode="before")
    @classmethod
    def validate_retention_from_one_to_36500_days(cls, value: Any, info: ValidationInfo) -> timedelta:
        """Read a number of days such as `30d` or an ISO 8601 duration such as `P30D`.

        Raises:
            ValueError: When the value is in neither form, is shorter than 1 day or is longer than 36500 days.

        """
        retention = _parse_retention(value)
        if retention is None:
            raise ValueError(
                f"Invalid task manager retention: {info.field_name} must be a number of days such as 30d "
                "or an ISO 8601 duration such as P30D"
            )
        if retention < _MINIMUM_RETENTION:
            raise ValueError(f"Invalid task manager retention: {info.field_name} must be at least 1 day")
        if retention > _MAXIMUM_RETENTION:
            raise ValueError(f"Invalid task manager retention: {info.field_name} must be at most 36500 days")
        return retention

    @model_validator(mode="after")
    def validate_prefect_own_events_within_activity_log(self) -> Self:
        """Require Prefect's own events to be kept no longer than the activity log.

        Raises:
            ValueError: When `prefect_own_events` is longer than `activity_log`.

        """
        if self.prefect_own_events > self.activity_log:
            raise ValueError(
                "Invalid task manager retention: prefect_own_events must not be longer than activity_log, "
                "so set prefect_own_events to at most the activity_log value"
            )
        return self


class TaskManagerSettings(BaseSettings):
    """How long the task manager keeps its task history and activity log."""

    model_config = SettingsConfigDict(env_prefix="INFRAHUB_TASK_MANAGER_")
    retention: TaskManagerRetentionSettings = Field(
        default_factory=TaskManagerRetentionSettings, description="How long each kind of record is kept."
    )


class _TaskManagerSection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    task_manager: TaskManagerSettings = Field(default_factory=TaskManagerSettings)


def load_task_manager_settings(config_file: Path) -> TaskManagerSettings:
    """Read the task manager settings from the configuration file and the environment, ignoring every other section.

    Raises:
        ValidationError: When a task manager setting is invalid.

    """
    data = tomllib.loads(config_file.read_text(encoding="utf-8")) if config_file.exists() else {}
    return _TaskManagerSection.model_validate(data).task_manager


def print_configuration_errors(error: ValidationError) -> None:
    """Print each error of an invalid configuration with its location."""
    print(f"Configuration not valid, found {len(error.errors())} error(s)")
    for details in error.errors():
        error_locations = [str(location) for location in details["loc"]]
        print(f"  {'/'.join(error_locations)} | {details['msg']} ({details['type']})")
