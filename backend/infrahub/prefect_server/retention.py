from __future__ import annotations

import json
from datetime import timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from infrahub.config import TaskManagerRetentionSettings

PREFECT_EVENT_TYPES: tuple[str, ...] = ()

VACUUM_ENABLED = "PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED"
VACUUM_RETENTION_PERIOD = "PREFECT_SERVER_SERVICES_DB_VACUUM_RETENTION_PERIOD"
EVENTS_RETENTION_PERIOD = "PREFECT_SERVER_EVENTS_RETENTION_PERIOD"
EVENT_RETENTION_OVERRIDES = "PREFECT_SERVER_SERVICES_DB_VACUUM_EVENT_RETENTION_OVERRIDES"

_RETENTION_KEY_OF_VARIABLE: dict[str, str] = {
    VACUUM_ENABLED: "task_history",
    VACUUM_RETENTION_PERIOD: "task_history",
    EVENTS_RETENTION_PERIOD: "activity_log",
    EVENT_RETENTION_OVERRIDES: "prefect_own_events",
}


def _iso_8601(duration: timedelta) -> str:
    # Days rather than years or months, whose length differs between ISO 8601 readers.
    days = f"P{duration.days}D"
    below_a_day = duration - timedelta(days=duration.days)
    if not below_a_day:
        return days
    seconds = f"{below_a_day.total_seconds():f}".rstrip("0").rstrip(".")
    return f"{days}T{seconds}S"


def _own_events_retention(settings: TaskManagerRetentionSettings) -> timedelta:
    # Prefect deletes every event older than the global event retention whatever its per-type override says.
    return min(settings.prefect_own_events, settings.activity_log)


def build_prefect_retention_env(settings: TaskManagerRetentionSettings, event_types: tuple[str, ...]) -> dict[str, str]:
    """Return the Prefect variables that enforce the retention.

    Args:
        event_types: Prefect event types kept for the own-event retention instead of the activity log retention.

    """
    own_events = _iso_8601(_own_events_retention(settings))
    return {
        VACUUM_ENABLED: "events,flow_runs",
        VACUUM_RETENTION_PERIOD: _iso_8601(settings.task_history),
        EVENTS_RETENTION_PERIOD: _iso_8601(settings.activity_log),
        EVENT_RETENTION_OVERRIDES: json.dumps(dict.fromkeys(event_types, own_events)),
    }


def apply_prefect_retention_env(environ: MutableMapping[str, str], settings: TaskManagerRetentionSettings) -> list[str]:
    """Set the retention variables that the environment does not already set, and return the warnings to log.

    A variable already present is left as it is, so an operator's explicit Prefect setting keeps precedence.
    """
    warnings: list[str] = []
    own_events = _own_events_retention(settings)
    if own_events < settings.prefect_own_events:
        warnings.append(
            f"task_manager.retention.prefect_own_events {_iso_8601(settings.prefect_own_events)} is longer than "
            f"task_manager.retention.activity_log {_iso_8601(settings.activity_log)}, "
            f"Prefect's own events are kept for {_iso_8601(own_events)}"
        )

    for name, value in build_prefect_retention_env(settings=settings, event_types=PREFECT_EVENT_TYPES).items():
        if name in environ:
            warnings.append(f"{name} is set and overrides task_manager.retention.{_RETENTION_KEY_OF_VARIABLE[name]}")
            continue
        environ[name] = value
    return warnings
