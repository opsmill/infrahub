from __future__ import annotations

import pytest

from infrahub.database.load_signal import (
    MIN_OBSERVATION_SECONDS,
    UNSTRESSED_RATIO,
    ReferenceQueryLoadTracker,
)
from infrahub.database.load_signal_metrics import LoadSignalMetricsObserver
from infrahub.database.metrics import (
    REFERENCE_QUERY_FLOOR_SECONDS,
    REFERENCE_QUERY_STRESS_RATIO_MEDIAN,
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


class RecordingLoadSignalObserver:
    """Load-signal sink that keeps every set of derived values pushed to it."""

    def __init__(self) -> None:
        self.observations: list[dict[str, float | None]] = []

    def on_observation(self, *, floor: float | None, window_min: float | None, stress_ratio_median: float) -> None:
        self.observations.append({"floor": floor, "window_min": window_min, "stress_ratio_median": stress_ratio_median})


class FailingLoadSignalObserver:
    """Load-signal sink that raises on every observation, to prove failures stay contained."""

    def on_observation(self, *, floor: float | None, window_min: float | None, stress_ratio_median: float) -> None:
        raise RuntimeError("observer blew up")


def test_empty_tracker_reads_as_unstressed() -> None:
    tracker = ReferenceQueryLoadTracker(observers=[], window_seconds=WINDOW, clock=FakeClock())

    assert tracker.floor() is None
    assert tracker.window_min() is None
    assert tracker.window_median() is None
    assert tracker.sample_count() == 0
    assert tracker.stress_ratio_median() == 1.0


def test_floor_is_absolute_running_minimum() -> None:
    tracker = ReferenceQueryLoadTracker(observers=[], window_seconds=WINDOW, clock=FakeClock())

    tracker.record(0.010)
    assert tracker.floor() == 0.010

    tracker.record(0.005)
    assert tracker.floor() == 0.005

    # A slower observation never raises the floor.
    tracker.record(0.020)
    assert tracker.floor() == 0.005


def test_window_evicts_samples_older_than_the_window() -> None:
    clock = FakeClock()
    tracker = ReferenceQueryLoadTracker(observers=[], window_seconds=WINDOW, clock=clock)

    tracker.record(0.010)  # t=0
    clock.advance(10)
    tracker.record(0.020)  # t=10
    clock.advance(25)
    tracker.record(0.030)  # t=35, horizon=5 → the t=0 sample falls out of the window

    assert tracker.sample_count() == 2
    assert tracker.window_min() == 0.020
    assert tracker.window_median() == pytest.approx((0.020 + 0.030) / 2)
    # The floor still remembers the evicted best observation.
    assert tracker.floor() == 0.010


def test_window_min_recovers_when_the_minimum_sample_is_evicted() -> None:
    clock = FakeClock()
    tracker = ReferenceQueryLoadTracker(observers=[], window_seconds=WINDOW, clock=clock)

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


def test_reads_expire_stale_window_after_idle_without_recording() -> None:
    # Regression: eviction was driven only by recording an observation, so after a stressed burst
    # the window stayed "stressed" through an idle gap — long enough to shed the first request that
    # arrived after the lull, before it could refresh the signal. A read must age the window itself.
    clock = FakeClock()
    tracker = ReferenceQueryLoadTracker(observers=[], window_seconds=WINDOW, clock=clock)

    tracker.record(0.001)  # sets the floor
    for _ in range(5):
        tracker.record(0.050)  # a stressed burst
    assert tracker.sample_count() == 6
    assert tracker.stress_ratio_median() > 1.0

    # Traffic goes idle: the clock advances past the window but nothing new is recorded.
    clock.advance(WINDOW + 1)

    assert tracker.sample_count() == 0
    assert tracker.window_min() is None
    assert tracker.window_median() is None
    assert tracker.stress_ratio_median() == UNSTRESSED_RATIO
    # The floor is absolute and survives the window emptying.
    assert tracker.floor() == 0.001


def test_stress_ratio_reflects_window_relative_to_floor() -> None:
    clock = FakeClock()
    tracker = ReferenceQueryLoadTracker(observers=[], window_seconds=WINDOW, clock=clock)

    tracker.record(0.001)  # t=0, sets the floor
    assert tracker.stress_ratio_median() == 1.0

    clock.advance(WINDOW + 1)
    tracker.record(0.010)  # the floor sample is now out of the window
    tracker.record(0.030)
    # Floor stays 0.001; the window min is 0.010 and the median is 0.020.
    assert tracker.window_min() == 0.010
    assert tracker.stress_ratio_median() == pytest.approx(20.0)


def test_window_median_ignores_outliers() -> None:
    # The whole reason for a median: a lone slow sample among fast ones barely moves it, so the
    # stress signal does not spike on a single GC pause or scheduling blip.
    clock = FakeClock()
    tracker = ReferenceQueryLoadTracker(observers=[], window_seconds=WINDOW, clock=clock)

    for _ in range(9):
        tracker.record(0.002)
    tracker.record(0.500)  # a single large outlier

    assert tracker.window_min() == 0.002
    assert tracker.window_median() == 0.002  # a mean would be pulled up to ~0.052


def test_sub_resolution_observations_are_clamped_to_the_floor() -> None:
    # A query timed faster than the clamp resolution must not become the floor.
    tracker = ReferenceQueryLoadTracker(observers=[], window_seconds=WINDOW, clock=FakeClock())

    tracker.record(0.0)
    assert tracker.floor() == MIN_OBSERVATION_SECONDS
    assert tracker.window_min() == MIN_OBSERVATION_SECONDS
    assert tracker.window_median() == MIN_OBSERVATION_SECONDS


def test_zero_baseline_then_load_still_moves_the_ratio() -> None:
    # Regression: a near-zero observation used to pin the floor to 0, which pinned every stress
    # ratio to 1.0 for the life of the process even under heavy load.
    clock = FakeClock()
    tracker = ReferenceQueryLoadTracker(observers=[], window_seconds=WINDOW, clock=clock)

    tracker.record(0.0)  # healthy, sub-resolution → clamped to the resolution floor
    assert tracker.stress_ratio_median() == 1.0

    clock.advance(WINDOW + 1)  # age the baseline sample out of the window
    for _ in range(5):
        tracker.record(0.020)  # 20 ms under load

    # Floor stays at the resolution; the window is entirely 20 ms, so the ratio climbs.
    assert tracker.floor() == MIN_OBSERVATION_SECONDS
    assert tracker.window_min() == 0.020
    assert tracker.stress_ratio_median() == pytest.approx(0.020 / MIN_OBSERVATION_SECONDS)


def test_observer_publishes_the_derived_signal_to_the_gauges() -> None:
    clock = FakeClock()
    tracker = ReferenceQueryLoadTracker(observers=[LoadSignalMetricsObserver()], window_seconds=WINDOW, clock=clock)

    tracker.record(0.002)  # a calm baseline sets the floor
    clock.advance(WINDOW + 1)  # age it out so the window reflects only the load
    tracker.record(0.050)

    assert REFERENCE_QUERY_FLOOR_SECONDS._value.get() == 0.002
    assert REFERENCE_QUERY_WINDOW_MIN_SECONDS._value.get() == 0.050
    assert REFERENCE_QUERY_STRESS_RATIO_MEDIAN._value.get() == pytest.approx(25.0)


def test_every_observer_receives_the_derived_signal() -> None:
    first = RecordingLoadSignalObserver()
    second = RecordingLoadSignalObserver()
    tracker = ReferenceQueryLoadTracker(observers=[first, second], window_seconds=WINDOW, clock=FakeClock())

    tracker.record(0.004)

    # Both sinks are pushed the derived values, so neither has to read back into the tracker.
    for observer in (first, second):
        assert observer.observations == [
            {"floor": 0.004, "window_min": 0.004, "stress_ratio_median": 1.0},
        ]


def test_failing_observer_does_not_fail_the_recording() -> None:
    survivor = RecordingLoadSignalObserver()
    # The failing sink is ordered first, so a shared guard would swallow the survivor too.
    tracker = ReferenceQueryLoadTracker(
        observers=[FailingLoadSignalObserver(), survivor], window_seconds=WINDOW, clock=FakeClock()
    )

    # record() runs on the database query path, so a raising sink must not propagate into the
    # query that fed the observation, and must not skip the sinks behind it.
    tracker.record(0.004)

    assert tracker.floor() == 0.004
    assert survivor.observations == [
        {"floor": 0.004, "window_min": 0.004, "stress_ratio_median": 1.0},
    ]
