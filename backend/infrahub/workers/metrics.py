from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from prometheus_client import Gauge, Histogram

if TYPE_CHECKING:
    from collections.abc import Iterator
    from datetime import datetime

METRIC_PREFIX = "infrahub_task"
UNKNOWN_QUEUE = "unknown"

FLOW_RUN_START_DELAY = Histogram(
    f"{METRIC_PREFIX}_flow_run_start_delay_seconds",
    "Time between the expected start of a flow run and the moment a task worker starts it",
    labelnames=["flow", "queue"],
    buckets=[1, 5, 15, 30, 60, 120, 300, 600, 1800, 3600],
)

# Each worker process counts only the runs it executes, so the processes alive now are summed.
FLOW_RUNS_IN_PROGRESS = Gauge(
    f"{METRIC_PREFIX}_flow_runs_in_progress",
    "Number of flow runs this task worker is running now",
    labelnames=["flow", "queue"],
    multiprocess_mode="livesum",
)


def _queue_label(queue: str | None) -> str:
    return queue or UNKNOWN_QUEUE


def observe_start_delay(
    flow: str, queue: str | None, expected_start_time: datetime | None, started_at: datetime
) -> None:
    """Record how long a flow run waited after its expected start time; a run without one records nothing."""
    if expected_start_time is None:
        return
    # A worker claims runs due within its prefetch window, so a run can start slightly before its expected time.
    delay = max((started_at - expected_start_time).total_seconds(), 0.0)
    FLOW_RUN_START_DELAY.labels(flow=flow, queue=_queue_label(queue)).observe(delay)


@contextmanager
def track_flow_run(flow: str, queue: str | None) -> Iterator[None]:
    """Count the flow run as in progress for the duration of the block, including when it raises."""
    gauge = FLOW_RUNS_IN_PROGRESS.labels(flow=flow, queue=_queue_label(queue))
    gauge.inc()
    try:
        yield
    finally:
        gauge.dec()
