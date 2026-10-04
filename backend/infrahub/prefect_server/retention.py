from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

from prefect.settings.models.server.events import ServerEventsSettings
from prefect.settings.models.server.services import ServerServicesDBVacuumSettings

if TYPE_CHECKING:
    from collections.abc import Mapping, MutableMapping

    from pydantic_settings import BaseSettings

    from infrahub.config import TaskManagerRetentionSettings

_STATE_NAMES = (
    "AwaitingConcurrencySlot",
    "AwaitingRetry",
    "Cached",
    "Cancelled",
    "Cancelling",
    "Completed",
    "Crashed",
    "Failed",
    "InfrastructurePending",
    "Late",
    "NotReady",
    "Paused",
    "Pending",
    "Resuming",
    "Retrying",
    "RolledBack",
    "Running",
    "Scheduled",
    "Submitting",
    "Suspended",
    "TimedOut",
)

# Read from the source of Prefect 3.8.6, whose per-type event retention matches event names exactly.
PREFECT_EVENT_TYPES: tuple[str, ...] = (
    *(f"prefect.{run}.{state}" for run in ("flow-run", "task-run") for state in _STATE_NAMES),
    "prefect.flow-run.heartbeat",
    "prefect.flow-run.pull-step.executed",
    "prefect.flow-run.pull-step.failed",
    "prefect.runner.cancelled-flow-run",
    "prefect.worker.started",
    "prefect.worker.stopped",
    "prefect.worker.submitted-flow-run",
    "prefect.worker.executed-flow-run",
    "prefect.flow.created",
    "prefect.flow.updated",
    "prefect.flow.deleted",
    "prefect.deployment.created",
    "prefect.deployment.updated",
    "prefect.deployment.deleted",
    "prefect.deployment.ready",
    "prefect.deployment.not-ready",
    "prefect.work-pool.created",
    "prefect.work-pool.updated",
    "prefect.work-pool.deleted",
    "prefect.work-pool.ready",
    "prefect.work-pool.not-ready",
    "prefect.work-pool.paused",
    "prefect.work-queue.created",
    "prefect.work-queue.updated",
    "prefect.work-queue.deleted",
    "prefect.work-queue.ready",
    "prefect.work-queue.not-ready",
    "prefect.work-queue.paused",
    "prefect.automation.created",
    "prefect.automation.updated",
    "prefect.automation.deleted",
    "prefect.automation.triggered",
    "prefect.automation.resolved",
    "prefect.automation.action.triggered",
    "prefect.automation.action.executed",
    "prefect.automation.action.failed",
    "prefect.block.redisstoragecontainer.loaded",
    "prefect.block-type.created",
    "prefect.block-type.updated",
    "prefect.block-type.deleted",
    "prefect.block-document.created",
    "prefect.block-document.updated",
    "prefect.block-document.deleted",
    "prefect.variable.created",
    "prefect.variable.updated",
    "prefect.variable.deleted",
    "prefect.concurrency-limit.created",
    "prefect.concurrency-limit.updated",
    "prefect.concurrency-limit.deleted",
    "prefect.concurrency-limit.acquired",
    "prefect.concurrency-limit.released",
    "prefect.concurrency-limit.v1.acquired",
    "prefect.concurrency-limit.v1.released",
    "prefect.artifact.created",
    "prefect.artifact.updated",
    "prefect.artifact-collection.created",
    "prefect.artifact-collection.updated",
    "prefect.artifact-collection.deleted",
    "prefect.asset.referenced",
    "prefect.asset.materialization.succeeded",
    "prefect.asset.materialization.failed",
)

VACUUM_ENABLED = "PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED"
VACUUM_RETENTION_PERIOD = "PREFECT_SERVER_SERVICES_DB_VACUUM_RETENTION_PERIOD"
EVENTS_RETENTION_PERIOD = "PREFECT_SERVER_EVENTS_RETENTION_PERIOD"
EVENT_RETENTION_OVERRIDES = "PREFECT_SERVER_SERVICES_DB_VACUUM_EVENT_RETENTION_OVERRIDES"


@dataclass(frozen=True)
class _PrefectSetting:
    model: type[BaseSettings]
    field: str
    retention_key: str

    def environment_names(self) -> list[str]:
        """Every environment variable Prefect reads the setting from, in the order Prefect tries them."""
        names: list[str] = self.model.model_json_schema()["properties"][self.field]["supported_environment_variables"]
        return names


_PREFECT_SETTINGS: dict[str, _PrefectSetting] = {
    VACUUM_ENABLED: _PrefectSetting(
        model=ServerServicesDBVacuumSettings, field="enabled", retention_key="task_history"
    ),
    VACUUM_RETENTION_PERIOD: _PrefectSetting(
        model=ServerServicesDBVacuumSettings, field="retention_period", retention_key="task_history"
    ),
    EVENTS_RETENTION_PERIOD: _PrefectSetting(
        model=ServerEventsSettings, field="retention_period", retention_key="activity_log"
    ),
    EVENT_RETENTION_OVERRIDES: _PrefectSetting(
        model=ServerServicesDBVacuumSettings, field="event_retention_overrides", retention_key="prefect_own_events"
    ),
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


def _name_set_in(environ: Mapping[str, str], setting: _PrefectSetting) -> str | None:
    # Prefect matches environment names case-insensitively and reads the first accepted name present.
    names_in_environ = {name.upper(): name for name in environ}
    for accepted in setting.environment_names():
        if accepted.upper() in names_in_environ:
            return names_in_environ[accepted.upper()]
    return None


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

    A Prefect setting already present under any name Prefect accepts for it is left as it is, so an operator's
    explicit Prefect setting keeps precedence.
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
        setting = _PREFECT_SETTINGS[name]
        name_set = _name_set_in(environ=environ, setting=setting)
        if name_set is not None:
            warnings.append(f"{name_set} is set and overrides task_manager.retention.{setting.retention_key}")
            continue
        environ[name] = value
    return warnings


def _count_overrides_per_retention(value: str) -> str:
    try:
        overrides = json.loads(value)
    except json.JSONDecodeError:
        return value
    if not isinstance(overrides, dict):
        return value
    per_retention = Counter(str(retention) for retention in overrides.values())
    return ", ".join(f"{retention} for {count} event types" for retention, count in sorted(per_retention.items()))


def prefect_retention_env_in_effect(environ: Mapping[str, str]) -> dict[str, str]:
    """Return the variable Prefect reads for each retention setting present in the environment, with its value.

    The per-type overrides are counted per retention rather than listed, as the list holds over a hundred types.
    """
    in_effect: dict[str, str] = {}
    for name, setting in _PREFECT_SETTINGS.items():
        name_set = _name_set_in(environ=environ, setting=setting)
        if name_set is None:
            continue
        value = environ[name_set]
        in_effect[name_set] = _count_overrides_per_retention(value) if name == EVENT_RETENTION_OVERRIDES else value
    return in_effect
