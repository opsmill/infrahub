from __future__ import annotations

import pytest

from infrahub.database.load_signal import (
    MIN_OBSERVATION_SECONDS,
    ReferenceQueryLoadTracker,
    _publish_metrics,
)
from infrahub.database.metrics import (
    REFERENCE_QUERY_FLOOR_SECONDS,
    REFERENCE_QUERY_STRESS_RATIO_MIN,
    REFERENCE_QUERY_WINDOW_MIN_SECONDS,
)

WINDOW = 30.0


class FakeClock:
    """Mutable monotonic clock advanced by hand; no real sleeps."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_empty_tracker_reads_as_unstressed() -> None:
    tracker = ReferenceQueryLoadTracker(window_seconds=WINDOW, clock=FakeClock())

    assert tracker.floor() is None
    assert tracker.window_min() is None
    assert tracker.window_avg() is None
    assert tracker.sample_count() == 0
    assert tracker.stress_ratio_min() == 1.0
    assert tracker.stress_ratio_avg() == 1.0


def test_floor_is_absolute_running_minimum() -> None:
    tracker = ReferenceQueryLoadTracker(window_seconds=WINDOW, clock=FakeClock())

    tracker.record(0.010)
    assert tracker.floor() == 0.010

    tracker.record(0.005)
    assert tracker.floor() == 0.005

    # A slower observation never raises the floor.
    tracker.record(0.020)
    assert tracker.floor() == 0.005


def test_window_evicts_samples_older_than_the_window() -> None:
    clock = FakeClock()
    tracker = ReferenceQueryLoadTracker(window_seconds=WINDOW, clock=clock)

    tracker.record(0.010)  # t=0
    clock.advance(10)
    tracker.record(0.020)  # t=10
    clock.advance(25)
    tracker.record(0.030)  # t=35, horizon=5 → the t=0 sample falls out of the window

    assert tracker.sample_count() == 2
    assert tracker.window_min() == 0.020
    assert tracker.window_avg() == pytest.approx((0.020 + 0.030) / 2)
    # The floor still remembers the evicted best observation.
    assert tracker.floor() == 0.010


def test_window_min_recovers_when_the_minimum_sample_is_evicted() -> None:
    clock = FakeClock()
    tracker = ReferenceQueryLoadTracker(window_seconds=WINDOW, clock=clock)

    tracker.record(0.002)  # t=0 (the eventual floor)
    clock.advance(5)
    tracker.record(0.008)  # t=5
    clock.advance(5)
    tracker.record(0.004)  # t=10
    assert tracker.window_min() == 0.002

    clock.advance(26)
    tracker.record(0.006)  # t=36, horizon=6 → the t=0 minimum leaves the window
    assert tracker.window_min() == 0.004
    assert tracker.floor() == 0.002


def test_stress_ratio_reflects_window_relative_to_floor() -> None:
    clock = FakeClock()
    tracker = ReferenceQueryLoadTracker(window_seconds=WINDOW, clock=clock)

    tracker.record(0.001)  # t=0, sets the floor
    assert tracker.stress_ratio_min() == 1.0

    clock.advance(WINDOW + 1)
    tracker.record(0.010)  # the floor sample is now out of the window
    tracker.record(0.030)
    # Floor stays 0.001; the window min is 0.010 and the average is 0.020.
    assert tracker.stress_ratio_min() == pytest.approx(10.0)
    assert tracker.stress_ratio_avg() == pytest.approx(20.0)


def test_sub_millisecond_observations_are_clamped_to_the_resolution() -> None:
    # Neo4j reports whole milliseconds, so a fast query reads as 0. It must not become the floor.
    tracker = ReferenceQueryLoadTracker(window_seconds=WINDOW, clock=FakeClock())

    tracker.record(0.0)
    assert tracker.floor() == MIN_OBSERVATION_SECONDS
    assert tracker.window_min() == MIN_OBSERVATION_SECONDS
    assert tracker.window_avg() == MIN_OBSERVATION_SECONDS


def test_zero_baseline_then_load_still_moves_the_ratio() -> None:
    # Regression: a 0 ms observation used to pin the floor to 0, which pinned every stress ratio
    # to 1.0 for the life of the process even under heavy load.
    clock = FakeClock()
    tracker = ReferenceQueryLoadTracker(window_seconds=WINDOW, clock=clock)

    tracker.record(0.0)  # healthy, sub-millisecond → clamped to the 1 ms floor
    assert tracker.stress_ratio_min() == 1.0

    clock.advance(WINDOW + 1)  # age the baseline sample out of the window
    for _ in range(5):
        tracker.record(0.020)  # 20 ms under load

    # Floor stays at the 1 ms resolution; the window is entirely 20 ms, so the ratio climbs.
    assert tracker.floor() == MIN_OBSERVATION_SECONDS
    assert tracker.window_min() == 0.020
    assert tracker.stress_ratio_min() == pytest.approx(0.020 / MIN_OBSERVATION_SECONDS)
    assert tracker.stress_ratio_avg() == pytest.approx(0.020 / MIN_OBSERVATION_SECONDS)


def test_observer_publishes_the_derived_signal_to_the_gauges() -> None:
    clock = FakeClock()
    tracker = ReferenceQueryLoadTracker(window_seconds=WINDOW, clock=clock)
    tracker.set_observer(_publish_metrics)

    tracker.record(0.002)  # a calm baseline sets the floor
    clock.advance(WINDOW + 1)  # age it out so the window reflects only the load
    tracker.record(0.050)

    assert REFERENCE_QUERY_FLOOR_SECONDS._value.get() == 0.002
    assert REFERENCE_QUERY_WINDOW_MIN_SECONDS._value.get() == 0.050
    assert REFERENCE_QUERY_STRESS_RATIO_MIN._value.get() == pytest.approx(25.0)
