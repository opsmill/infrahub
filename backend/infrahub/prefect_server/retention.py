from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

from prefect.settings.models.server.events import ServerEventsSettings
from prefect.settings.models.server.services import ServerServicesDBVacuumSettings

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, MutableMapping

    from prefect.settings import Settings
    from pydantic_settings import BaseSettings

    from .retention_settings import TaskManagerRetentionSettings

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
    "Rerunning",
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
    "prefect.workspace.transfer.started",
    "prefect.workspace.transfer.completed",
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

PREFECT_EVENT_PREFIX = "prefect."


def unlisted_prefect_event_types_warning(stored_event_types: Iterable[str], event_retention: timedelta) -> str | None:
    """Return the warning naming the stored Prefect event types missing from the list, or None when every one is listed.

    Args:
        event_retention: The event retention Prefect applies, which keeps the missing types.

    """
    prefect_event_types = {
        event_type for event_type in stored_event_types if event_type.startswith(PREFECT_EVENT_PREFIX)
    }
    unlisted = sorted(prefect_event_types.difference(PREFECT_EVENT_TYPES))
    if not unlisted:
        return None
    return (
        "Task manager retention: Infrahub does not list these Prefect event types, so they are kept for the activity "
        f"log retention ({_iso_8601(event_retention)}) instead of prefect_own_events: {', '.join(unlisted)}"
    )


VACUUM_ENABLED = "PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED"
VACUUM_RETENTION_PERIOD = "PREFECT_SERVER_SERVICES_DB_VACUUM_RETENTION_PERIOD"
EVENTS_RETENTION_PERIOD = "PREFECT_SERVER_EVENTS_RETENTION_PERIOD"
EVENT_RETENTION_OVERRIDES = "PREFECT_SERVER_SERVICES_DB_VACUUM_EVENT_RETENTION_OVERRIDES"
WEBSERVER_ONLY = "PREFECT__SERVER_WEBSERVER_ONLY"


@dataclass(frozen=True)
class _PrefectSetting:
    model: type[BaseSettings]
    field: str
    overridden_retention: str | None

    def environment_names(self) -> list[str]:
        """Every environment variable Prefect reads the setting from, in the order Prefect tries them."""
        names: list[str] = self.model.model_json_schema()["properties"][self.field]["supported_environment_variables"]
        return names


_PREFECT_SETTINGS: dict[str, _PrefectSetting] = {
    # The switch turns cleanups on or off and replaces no retention.
    VACUUM_ENABLED: _PrefectSetting(model=ServerServicesDBVacuumSettings, field="enabled", overridden_retention=None),
    VACUUM_RETENTION_PERIOD: _PrefectSetting(
        model=ServerServicesDBVacuumSettings, field="retention_period", overridden_retention="task_history"
    ),
    EVENTS_RETENTION_PERIOD: _PrefectSetting(
        model=ServerEventsSettings, field="retention_period", overridden_retention="activity_log"
    ),
    EVENT_RETENTION_OVERRIDES: _PrefectSetting(
        model=ServerServicesDBVacuumSettings,
        field="event_retention_overrides",
        overridden_retention="prefect_own_events",
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


def _name_set_in(environ: Mapping[str, str], setting: _PrefectSetting) -> str | None:
    # Prefect matches environment names case-insensitively and reads the first accepted name present.
    names_in_environ = {name.upper(): name for name in environ}
    for accepted in setting.environment_names():
        if accepted.upper() in names_in_environ:
            return names_in_environ[accepted.upper()]
    return None


def remove_blank_vacuum_switch(environ: MutableMapping[str, str]) -> None:
    """Remove the vacuum switch when it is present but empty or blank, under any name Prefect accepts for it."""
    # A compose file passes an unset host variable as an empty value, which Prefect reads as false for this switch
    # and so deletes no task runs, while an empty retention variable already made the import of Prefect fail.
    accepted = {name.upper() for name in _PREFECT_SETTINGS[VACUUM_ENABLED].environment_names()}
    for name in [name for name in environ if name.upper() in accepted and not environ[name].strip()]:
        del environ[name]


def build_prefect_retention_env(settings: TaskManagerRetentionSettings, event_types: tuple[str, ...]) -> dict[str, str]:
    """Return the Prefect variables that enforce the retention.

    Args:
        event_types: Prefect event types kept for the own-event retention instead of the activity log retention.
            No type gives an empty mapping, which also replaces Prefect's default override for heartbeats.

    """
    own_events = _iso_8601(settings.prefect_own_events)
    return {
        VACUUM_ENABLED: "events,flow_runs",
        VACUUM_RETENTION_PERIOD: _iso_8601(settings.task_history),
        EVENTS_RETENTION_PERIOD: _iso_8601(settings.activity_log),
        EVENT_RETENTION_OVERRIDES: json.dumps(dict.fromkeys(event_types, own_events)),
    }


def prefect_retention_already_set() -> frozenset[str]:
    """Return the retention variables whose Prefect setting a Prefect source already sets.

    Prefect reads a setting from the environment, a `.env` file, `prefect.toml`, the `[tool.prefect]` table of
    `pyproject.toml` or the active profile, and marks a field as set only when one of them supplies it. An empty
    vacuum switch counts as set, so the caller removes a blank one first.
    """
    return frozenset(
        name for name, setting in _PREFECT_SETTINGS.items() if setting.field in setting.model().model_fields_set
    )


def apply_prefect_retention_env(
    environ: MutableMapping[str, str], settings: TaskManagerRetentionSettings, already_set: frozenset[str]
) -> list[str]:
    """Set the retention variables whose Prefect setting no Prefect source sets, and return the warnings to log.

    A Prefect setting that is already set is left as it is, so an operator's explicit Prefect setting keeps
    precedence, with a warning when it replaces a retention. The per-type event overrides are written as an empty
    mapping when they cannot shorten the event retention that Infrahub writes.

    Args:
        already_set: Retention variables whose Prefect setting the environment, a Prefect settings file or the
            active profile already sets, read before any variable is written.

    """
    # Prefect deletes every event older than the general retention anyway, so overrides that are not shorter only
    # add delete queries.
    write_overrides = EVENTS_RETENTION_PERIOD in already_set or settings.prefect_own_events < settings.activity_log
    event_types = PREFECT_EVENT_TYPES if write_overrides else ()
    warnings: list[str] = []
    for name, value in build_prefect_retention_env(settings=settings, event_types=event_types).items():
        if name not in already_set:
            environ[name] = value
            continue
        setting = _PREFECT_SETTINGS[name]
        if setting.overridden_retention is None:
            continue
        overrides = f"overrides task_manager.retention.{setting.overridden_retention}"
        name_set = _name_set_in(environ=environ, setting=setting)
        if name_set is None:
            warnings.append(f"{name} is set in a Prefect settings file or profile and {overrides}")
        else:
            warnings.append(f"{name_set} is set and {overrides}")
    return warnings


def background_services_warning(environ: Mapping[str, str]) -> str | None:
    """Return the warning to log when Prefect's background services, which delete old records, run in another process."""
    # Prefect's server reads any non-empty value of this variable as true, "false" included.
    if not environ.get(WEBSERVER_ONLY):
        return None
    return (
        f"Task manager retention: {WEBSERVER_ONLY} is set, so this process does not run Prefect's background "
        "services, which delete old task runs and events. The process that runs them, such as "
        "`prefect server services start`, does not read task_manager.retention: unless it sets the same PREFECT_* "
        "variables, it deletes no task runs and keeps events for Prefect's default of 7 days."
    )


def turned_off_cleanup_warnings(vacuum: ServerServicesDBVacuumSettings) -> list[str]:
    """Return a warning for each of Prefect's cleanups that the vacuum switch turns off, naming the retention not applied."""
    try:
        enabled = vacuum.enabled_vacuum_types
    except ValueError as exc:
        # Prefect checks the vacuum types only when its services read them, so an unknown one is named here and
        # the failure is left to Prefect.
        return [f"{VACUUM_ENABLED} is not valid: {exc}"]
    warnings: list[str] = []
    if "flow_runs" not in enabled:
        warnings.append(
            f"{VACUUM_ENABLED} does not turn on flow_runs, so old task runs are not deleted and "
            "task_manager.retention.task_history is not applied"
        )
    if "events" not in enabled:
        warnings.append(
            f"{VACUUM_ENABLED} does not turn on events, so old events are not deleted and "
            "task_manager.retention.activity_log and task_manager.retention.prefect_own_events are not applied"
        )
    return warnings


def task_run_deletion_off_reason(vacuum: ServerServicesDBVacuumSettings) -> str | None:
    """Return why Prefect's vacuum switch keeps old task runs, or None when it turns their deletion on."""
    try:
        enabled = vacuum.enabled_vacuum_types
    except ValueError as exc:
        # Prefect checks the vacuum types only when its services read them, so its settings load with an unknown one.
        return f"{VACUUM_ENABLED} is not valid: {exc}"
    if "flow_runs" not in enabled:
        return f"{VACUUM_ENABLED} does not turn on flow_runs"
    return None


def deletes_old_events(vacuum: ServerServicesDBVacuumSettings) -> bool:
    """Return whether Prefect's vacuum switch turns on the deletion of old events."""
    try:
        return "events" in vacuum.enabled_vacuum_types
    except ValueError:
        # With an unknown vacuum type it is not known whether old events are deleted, so they are treated as kept.
        return False


def _vacuum_switch(enabled: set[str] | bool | None) -> str:
    if isinstance(enabled, bool):
        return "true" if enabled else "false"
    if enabled is None:
        return "null"
    return ",".join(sorted(enabled)) or "[]"


def _count_overrides_per_retention(overrides: Mapping[str, timedelta]) -> str:
    if not overrides:
        return "{}"
    per_retention = Counter(overrides.values())
    return ", ".join(
        f"{_iso_8601(retention)} for {count} event types" for retention, count in sorted(per_retention.items())
    )


def prefect_retention_in_effect(settings: Settings) -> dict[str, str]:
    """Return the value Prefect applies for each retention setting, keyed by the variable Infrahub derives for it.

    The per-type overrides are counted per retention rather than listed, as the list holds over a hundred types.
    """
    vacuum = settings.server.services.db_vacuum
    return {
        VACUUM_ENABLED: _vacuum_switch(enabled=vacuum.enabled),
        VACUUM_RETENTION_PERIOD: _iso_8601(vacuum.retention_period),
        EVENTS_RETENTION_PERIOD: _iso_8601(settings.server.events.retention_period),
        EVENT_RETENTION_OVERRIDES: _count_overrides_per_retention(overrides=vacuum.event_retention_overrides),
    }
