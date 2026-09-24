from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from prefect.client.schemas.objects import StateType

from infrahub.task_manager.scheduled_flow.health import ASSUMED_RUN_RETENTION_DAYS, assess_health
from infrahub.task_manager.scheduled_flow.models import LatestRunInfo, ScheduledFlowHealth

NOW = datetime(2026, 9, 24, 7, 30, tzinfo=UTC)
MINUTE = 60
DAY = 86400


def executed_run(
    *,
    state_type: StateType,
    expected_start_time: datetime,
    started: bool = True,
) -> LatestRunInfo:
    return LatestRunInfo(
        id=uuid4(),
        state_type=state_type,
        state_name=state_type.value.title(),
        expected_start_time=expected_start_time,
        start_time=expected_start_time if started else None,
        end_time=expected_start_time if started else None,
    )


@dataclass
class HealthCase:
    name: str
    latest_run: LatestRunInfo | None
    interval_seconds: int | None
    active: bool
    deployment_created_at: datetime | None
    expected: ScheduledFlowHealth


CASES = [
    HealthCase(
        name="every_minute_worker_alive_last_run_completed_30s_ago",
        latest_run=executed_run(state_type=StateType.COMPLETED, expected_start_time=NOW - timedelta(seconds=30)),
        interval_seconds=MINUTE,
        active=True,
        deployment_created_at=NOW - timedelta(days=10),
        expected=ScheduledFlowHealth.HEALTHY,
    ),
    HealthCase(
        # The motivating incident: the scheduler keeps pre-creating future runs while no worker
        # consumes them, so only the newest executed run reveals the stall.
        name="every_minute_worker_stopped_three_days_ago",
        latest_run=executed_run(state_type=StateType.COMPLETED, expected_start_time=NOW - timedelta(days=3)),
        interval_seconds=MINUTE,
        active=True,
        deployment_created_at=NOW - timedelta(days=30),
        expected=ScheduledFlowHealth.OVERDUE,
    ),
    HealthCase(
        name="every_minute_with_no_executed_run_at_all",
        latest_run=None,
        interval_seconds=MINUTE,
        active=True,
        deployment_created_at=NOW - timedelta(days=5),
        expected=ScheduledFlowHealth.OVERDUE,
    ),
    HealthCase(
        name="every_minute_ticks_being_cancelled_by_a_collision",
        latest_run=executed_run(
            state_type=StateType.CANCELLED, expected_start_time=NOW - timedelta(seconds=45), started=False
        ),
        interval_seconds=MINUTE,
        active=True,
        deployment_created_at=NOW - timedelta(days=5),
        expected=ScheduledFlowHealth.CANCELLED,
    ),
    HealthCase(
        name="latest_run_failed",
        latest_run=executed_run(state_type=StateType.FAILED, expected_start_time=NOW - timedelta(seconds=30)),
        interval_seconds=MINUTE,
        active=True,
        deployment_created_at=NOW - timedelta(days=5),
        expected=ScheduledFlowHealth.FAILED,
    ),
    HealthCase(
        name="latest_run_crashed_counts_as_failed",
        latest_run=executed_run(state_type=StateType.CRASHED, expected_start_time=NOW - timedelta(seconds=30)),
        interval_seconds=MINUTE,
        active=True,
        deployment_created_at=NOW - timedelta(days=5),
        expected=ScheduledFlowHealth.FAILED,
    ),
    HealthCase(
        name="daily_flow_registered_two_hours_ago_with_no_runs",
        latest_run=None,
        interval_seconds=DAY,
        active=True,
        deployment_created_at=NOW - timedelta(hours=2),
        expected=ScheduledFlowHealth.NEVER_RUN,
    ),
    HealthCase(
        name="every_minute_flow_registered_ten_seconds_ago_with_no_runs",
        latest_run=None,
        interval_seconds=MINUTE,
        active=True,
        deployment_created_at=NOW - timedelta(seconds=10),
        expected=ScheduledFlowHealth.NEVER_RUN,
    ),
    HealthCase(
        name="uninterpretable_cron_with_no_executed_runs",
        latest_run=None,
        interval_seconds=None,
        active=True,
        deployment_created_at=NOW - timedelta(days=5),
        expected=ScheduledFlowHealth.NO_RECENT_RUNS,
    ),
    HealthCase(
        name="no_executed_runs_and_unknown_deployment_age",
        latest_run=None,
        interval_seconds=DAY,
        active=True,
        deployment_created_at=None,
        expected=ScheduledFlowHealth.NO_RECENT_RUNS,
    ),
    HealthCase(
        name="no_executed_runs_on_a_deployment_older_than_the_assumed_retention_window",
        latest_run=None,
        # A schedule whose overdue window exceeds the retention window is the only shape where the
        # absence of runs is genuinely inconclusive rather than late.
        interval_seconds=DAY * 365,
        active=True,
        deployment_created_at=NOW - timedelta(days=ASSUMED_RUN_RETENTION_DAYS + 1),
        expected=ScheduledFlowHealth.NO_RECENT_RUNS,
    ),
    HealthCase(
        name="paused_schedule_that_is_also_late",
        latest_run=executed_run(state_type=StateType.COMPLETED, expected_start_time=NOW - timedelta(days=3)),
        interval_seconds=MINUTE,
        active=False,
        deployment_created_at=NOW - timedelta(days=30),
        expected=ScheduledFlowHealth.PAUSED,
    ),
    HealthCase(
        name="paused_schedule_whose_last_run_failed",
        latest_run=executed_run(state_type=StateType.FAILED, expected_start_time=NOW - timedelta(seconds=30)),
        interval_seconds=MINUTE,
        active=False,
        deployment_created_at=NOW - timedelta(days=30),
        expected=ScheduledFlowHealth.PAUSED,
    ),
    HealthCase(
        name="paused_schedule_with_no_executed_runs",
        latest_run=None,
        interval_seconds=DAY,
        active=False,
        deployment_created_at=NOW - timedelta(hours=2),
        expected=ScheduledFlowHealth.PAUSED,
    ),
    HealthCase(
        name="overdue_outranks_a_failed_last_run",
        latest_run=executed_run(state_type=StateType.FAILED, expected_start_time=NOW - timedelta(days=3)),
        interval_seconds=MINUTE,
        active=True,
        deployment_created_at=NOW - timedelta(days=30),
        expected=ScheduledFlowHealth.OVERDUE,
    ),
]


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_assess_health(case: HealthCase) -> None:
    verdict = assess_health(
        latest_run=case.latest_run,
        interval_seconds=case.interval_seconds,
        active=case.active,
        deployment_created_at=case.deployment_created_at,
        now=NOW,
    )

    assert verdict == case.expected


def test_a_run_cancelled_before_it_started_is_cancelled_and_never_failed() -> None:
    run = executed_run(state_type=StateType.CANCELLED, expected_start_time=NOW - timedelta(seconds=30), started=False)
    assert run.start_time is None

    verdict = assess_health(
        latest_run=run,
        interval_seconds=MINUTE,
        active=True,
        deployment_created_at=NOW - timedelta(days=5),
        now=NOW,
    )

    assert verdict == ScheduledFlowHealth.CANCELLED
