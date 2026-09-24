from datetime import datetime, timedelta

from prefect.client.schemas.objects import StateType

from .models import LatestRunInfo, ScheduledFlowHealth

# How long run history is assumed to survive, used only to tell "never ran" apart from "history
# purged". It is a constant rather than a setting because nothing persists a retention cadence:
# purging happens only when an operator invokes the CLI. A wrong value can only flip between
# NEVER_RUN and NO_RECENT_RUNS — two ways of saying "no history to show you" — because no other
# verdict consults it.
ASSUMED_RUN_RETENTION_DAYS = 30

# A flow is late once it has missed this many of its own intervals.
OVERDUE_INTERVAL_MULTIPLIER = 3

FAILED_STATES = frozenset({StateType.FAILED, StateType.CRASHED})
CANCELLED_STATES = frozenset({StateType.CANCELLED, StateType.CANCELLING})


def assess_health(
    *,
    latest_run: LatestRunInfo | None,
    interval_seconds: int | None,
    active: bool,
    deployment_created_at: datetime | None,
    now: datetime,
) -> ScheduledFlowHealth:
    """Derive a scheduled flow's health from its newest executed run and its schedule.

    `latest_run` is the newest run that was due by `now` and got past the queue, so `None` means no
    run has executed — never that the deployment has no rows, which is never true while Prefect
    pre-creates future runs.
    """
    if not active:
        return ScheduledFlowHealth.PAUSED

    if _is_overdue(
        latest_run=latest_run,
        interval_seconds=interval_seconds,
        deployment_created_at=deployment_created_at,
        now=now,
    ):
        return ScheduledFlowHealth.OVERDUE

    if latest_run is not None:
        return _verdict_from_latest_run(latest_run)

    return _verdict_without_executed_runs(
        interval_seconds=interval_seconds, deployment_created_at=deployment_created_at, now=now
    )


def _is_overdue(
    *,
    latest_run: LatestRunInfo | None,
    interval_seconds: int | None,
    deployment_created_at: datetime | None,
    now: datetime,
) -> bool:
    if not interval_seconds or deployment_created_at is None:
        return False

    overdue_window = timedelta(seconds=interval_seconds * OVERDUE_INTERVAL_MULTIPLIER)
    # A flow registered less than one overdue window ago has simply not come due yet.
    if now - deployment_created_at < overdue_window:
        return False

    if latest_run is None:
        return True
    if latest_run.expected_start_time is None:
        return False
    return latest_run.expected_start_time < now - overdue_window


def _verdict_from_latest_run(latest_run: LatestRunInfo) -> ScheduledFlowHealth:
    if latest_run.state_type in FAILED_STATES:
        return ScheduledFlowHealth.FAILED
    if latest_run.state_type in CANCELLED_STATES:
        return ScheduledFlowHealth.CANCELLED
    return ScheduledFlowHealth.HEALTHY


def _verdict_without_executed_runs(
    *, interval_seconds: int | None, deployment_created_at: datetime | None, now: datetime
) -> ScheduledFlowHealth:
    deployment_age_is_conclusive = (
        interval_seconds is not None
        and deployment_created_at is not None
        and now - deployment_created_at < timedelta(days=ASSUMED_RUN_RETENTION_DAYS)
    )
    if deployment_age_is_conclusive:
        return ScheduledFlowHealth.NEVER_RUN
    return ScheduledFlowHealth.NO_RECENT_RUNS
