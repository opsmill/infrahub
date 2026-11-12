from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from prometheus_client import REGISTRY

from infrahub.workers.metrics import FLOW_RUN_START_DELAY, observe_start_delay, track_flow_run
from tests.helpers.metrics import bucket_bounds

START_DELAY = "infrahub_task_flow_run_start_delay_seconds"
IN_PROGRESS = "infrahub_task_flow_runs_in_progress"
EXPECTED_START = datetime(2026, 10, 13, 12, 0, 0, tzinfo=UTC)


def _delay_count(flow: str, queue: str) -> float | None:
    return REGISTRY.get_sample_value(f"{START_DELAY}_count", {"flow": flow, "queue": queue})


def _delay_sum(flow: str, queue: str) -> float | None:
    return REGISTRY.get_sample_value(f"{START_DELAY}_sum", {"flow": flow, "queue": queue})


def _in_progress(flow: str, queue: str) -> float | None:
    return REGISTRY.get_sample_value(IN_PROGRESS, {"flow": flow, "queue": queue})


def test_start_delay_is_the_real_start_minus_the_expected_start() -> None:
    observe_start_delay(
        flow="delay-probe",
        queue="high",
        expected_start_time=EXPECTED_START,
        started_at=EXPECTED_START + timedelta(seconds=42),
    )

    assert _delay_count(flow="delay-probe", queue="high") == 1
    assert _delay_sum(flow="delay-probe", queue="high") == 42
    assert (
        REGISTRY.get_sample_value(f"{START_DELAY}_bucket", {"flow": "delay-probe", "queue": "high", "le": "30.0"}) == 0
    )
    assert (
        REGISTRY.get_sample_value(f"{START_DELAY}_bucket", {"flow": "delay-probe", "queue": "high", "le": "60.0"}) == 1
    )


def test_run_started_before_its_expected_start_records_no_wait() -> None:
    observe_start_delay(
        flow="early-probe",
        queue="medium",
        expected_start_time=EXPECTED_START,
        started_at=EXPECTED_START - timedelta(seconds=5),
    )

    assert _delay_count(flow="early-probe", queue="medium") == 1
    assert _delay_sum(flow="early-probe", queue="medium") == 0


def test_run_without_expected_start_records_no_delay() -> None:
    observe_start_delay(flow="no-expected-probe", queue="low", expected_start_time=None, started_at=EXPECTED_START)

    assert _delay_count(flow="no-expected-probe", queue="low") is None


def test_run_without_queue_name_is_labelled_unknown() -> None:
    observe_start_delay(
        flow="no-queue-probe", queue=None, expected_start_time=EXPECTED_START, started_at=EXPECTED_START
    )
    with track_flow_run(flow="no-queue-probe", queue=None):
        assert _in_progress(flow="no-queue-probe", queue="unknown") == 1

    assert _delay_count(flow="no-queue-probe", queue="unknown") == 1


def test_start_delay_is_recorded_up_to_one_hour() -> None:
    observe_start_delay(flow="bounds-probe", queue="low", expected_start_time=EXPECTED_START, started_at=EXPECTED_START)

    assert bucket_bounds(FLOW_RUN_START_DELAY, labels={"flow": "bounds-probe", "queue": "low"}) == [
        "1.0",
        "5.0",
        "15.0",
        "30.0",
        "60.0",
        "120.0",
        "300.0",
        "600.0",
        "1800.0",
        "3600.0",
    ]


def test_runs_in_progress_rises_during_the_run_and_falls_after_it() -> None:
    with track_flow_run(flow="progress-probe", queue="high"):
        assert _in_progress(flow="progress-probe", queue="high") == 1
        with track_flow_run(flow="progress-probe", queue="high"):
            assert _in_progress(flow="progress-probe", queue="high") == 2

    assert _in_progress(flow="progress-probe", queue="high") == 0


def _fail_while_tracked(flow: str, queue: str, seen: list[float | None]) -> None:
    with track_flow_run(flow=flow, queue=queue):
        seen.append(_in_progress(flow=flow, queue=queue))
        raise RuntimeError("flow failed")


def test_runs_in_progress_falls_when_the_run_raises() -> None:
    seen: list[float | None] = []

    with pytest.raises(RuntimeError, match="flow failed"):
        _fail_while_tracked(flow="failing-probe", queue="medium", seen=seen)

    assert seen == [1]
    assert _in_progress(flow="failing-probe", queue="medium") == 0
