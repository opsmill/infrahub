from __future__ import annotations

from infrahub.database.load_signal_metrics import LoadSignalMetricsObserver
from infrahub.database.metrics import (
    REFERENCE_QUERY_FLOOR_SECONDS,
    REFERENCE_QUERY_STRESS_RATIO_MEDIAN,
    REFERENCE_QUERY_WINDOW_MIN_SECONDS,
)


def test_derived_signal_reaches_its_gauges() -> None:
    LoadSignalMetricsObserver().on_observation(floor=0.002, window_min=0.050, stress_ratio_median=25.0)

    assert REFERENCE_QUERY_FLOOR_SECONDS._value.get() == 0.002
    assert REFERENCE_QUERY_WINDOW_MIN_SECONDS._value.get() == 0.050
    assert REFERENCE_QUERY_STRESS_RATIO_MEDIAN._value.get() == 25.0


def test_undefined_values_leave_their_gauges_untouched() -> None:
    observer = LoadSignalMetricsObserver()
    observer.on_observation(floor=0.004, window_min=0.010, stress_ratio_median=2.5)

    # A tracker with an empty window reports no floor and no window minimum. Zeroing those gauges
    # would read as a genuine measurement of zero, so the last known values have to stand.
    observer.on_observation(floor=None, window_min=None, stress_ratio_median=1.0)

    assert REFERENCE_QUERY_FLOOR_SECONDS._value.get() == 0.004
    assert REFERENCE_QUERY_WINDOW_MIN_SECONDS._value.get() == 0.010
    # The ratio is always defined, so it does follow the new observation.
    assert REFERENCE_QUERY_STRESS_RATIO_MEDIAN._value.get() == 1.0
