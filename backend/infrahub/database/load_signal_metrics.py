from __future__ import annotations

from .metrics import (
    REFERENCE_QUERY_FLOOR_SECONDS,
    REFERENCE_QUERY_STRESS_RATIO_MEDIAN,
    REFERENCE_QUERY_WINDOW_MIN_SECONDS,
)


class LoadSignalMetricsObserver:
    """Publishes the derived database-stress signal onto the Prometheus gauges."""

    def on_observation(self, *, floor: float | None, window_min: float | None, stress_ratio_median: float) -> None:
        # A gauge is left untouched rather than zeroed while the corresponding value is still
        # undefined, so an unset figure never reads as a real measurement of zero.
        if floor is not None:
            REFERENCE_QUERY_FLOOR_SECONDS.set(floor)
        if window_min is not None:
            REFERENCE_QUERY_WINDOW_MIN_SECONDS.set(window_min)
        REFERENCE_QUERY_STRESS_RATIO_MEDIAN.set(stress_ratio_median)
