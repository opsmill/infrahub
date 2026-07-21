from __future__ import annotations

import time
from collections import deque
from typing import Callable, Protocol

from .metrics import (
    REFERENCE_QUERY_FLOOR_SECONDS,
    REFERENCE_QUERY_STRESS_RATIO_AVG,
    REFERENCE_QUERY_STRESS_RATIO_MIN,
    REFERENCE_QUERY_WINDOW_MIN_SECONDS,
)

DEFAULT_STRESS_WINDOW_SECONDS = 20.0

# Ratio returned before there is a usable floor to divide by. 1.0 reads as "unstressed", so a
# cold tracker never trips a stress-ratio gate.
UNSTRESSED_RATIO = 1.0

# An observation is clamped up to this minimum before it is recorded. A query timed at
# effectively zero (measurement noise, or a round-trip faster than the timer's useful
# resolution) must not become the floor: a near-zero floor would peg the stress ratio at 1.0
# (nothing divided by it ever exceeds it) or make the ratio undefined, so the signal could
# never move. 10 us is below any realistic database round-trip, so it never clamps a genuine one.
MIN_OBSERVATION_SECONDS = 0.00001


class LoadSignal(Protocol):
    """The database-stress view the admission layer consumes.

    Kept minimal so the admission gate can be exercised with a hand-built stand-in rather
    than a live tracker.
    """

    def stress_ratio_min(self) -> float: ...

    def stress_ratio_avg(self) -> float: ...

    def sample_count(self) -> int: ...


class ReferenceQueryLoadTracker:
    """Rolling database-stress signal derived from the reference query's execution time.

    Every reference-query observation feeds :meth:`record`. The tracker keeps the all-time
    minimum ("floor") plus a rolling window of the most recent ``window_seconds`` of samples,
    and derives how much slower the database currently is than at its best. A stress ratio of
    ``5`` means even the fastest recent query took five times the floor: sustained load.

    State is per worker process and lives on a single asyncio event loop, so — like the
    admission slot pool — it takes no lock: ``record`` never awaits, so no two updates
    interleave. Both the window minimum and the window average are maintained incrementally so
    each observation is O(1) amortized rather than an O(n) scan, which matters when the window
    holds tens of thousands of samples under load.

    The floor is an absolute running minimum: a single anomalously fast observation lowers it
    permanently. That is intentional (it is the best the database has ever demonstrated), at
    the cost of never recovering from a spurious outlier until the process restarts.
    """

    def __init__(
        self,
        *,
        window_seconds: float = DEFAULT_STRESS_WINDOW_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.window_seconds = window_seconds
        self._clock = clock
        self._floor: float | None = None
        # Every in-window sample, for the average (running sum / count).
        self._samples: deque[tuple[float, float]] = deque()
        self._running_sum = 0.0
        # A monotonic-increasing-by-value deque; its front is the window minimum. Values that
        # can never again be the minimum (an equal-or-larger older sample) are dropped on push.
        self._window_min: deque[tuple[float, float]] = deque()
        self._observer: Callable[[ReferenceQueryLoadTracker], None] | None = None

    def set_observer(self, observer: Callable[[ReferenceQueryLoadTracker], None] | None) -> None:
        """Register a callback invoked after each recorded observation.

        Lets an external sink (the metric gauges) refresh from the latest state without the
        tracker depending on that sink.
        """
        self._observer = observer

    def record(self, execution_seconds: float) -> None:
        """Record one reference-query observation and refresh the derived signal.

        The observation is clamped up to a minimum: a query timed at effectively zero would
        otherwise leave the stress ratio permanently pinned at ``1.0``.

        Args:
            execution_seconds: Measured execution time of the query, from submission through
                draining the result, in seconds.

        """
        now = self._clock()
        observation = max(execution_seconds, MIN_OBSERVATION_SECONDS)

        if self._floor is None or observation < self._floor:
            self._floor = observation

        self._samples.append((now, observation))
        self._running_sum += observation

        while self._window_min and self._window_min[-1][1] >= observation:
            self._window_min.pop()
        self._window_min.append((now, observation))

        self._evict(now=now)

        if self._observer is not None:
            self._observer(self)

    def _evict(self, *, now: float) -> None:
        horizon = now - self.window_seconds
        while self._samples and self._samples[0][0] <= horizon:
            self._running_sum -= self._samples.popleft()[1]
        while self._window_min and self._window_min[0][0] <= horizon:
            self._window_min.popleft()

    def floor(self) -> float | None:
        """The all-time minimum observation, or ``None`` before any observation."""
        return self._floor

    def sample_count(self) -> int:
        """Number of observations currently inside the window."""
        return len(self._samples)

    def window_min(self) -> float | None:
        """The minimum observation within the window, or ``None`` when the window is empty."""
        if not self._window_min:
            return None
        return self._window_min[0][1]

    def window_avg(self) -> float | None:
        """The mean observation within the window, or ``None`` when the window is empty."""
        if not self._samples:
            return None
        return self._running_sum / len(self._samples)

    def stress_ratio_min(self) -> float:
        """Window minimum divided by the floor; ``1.0`` when there is nothing to compare."""
        return self._ratio(self.window_min())

    def stress_ratio_avg(self) -> float:
        """Window average divided by the floor; ``1.0`` when there is nothing to compare."""
        return self._ratio(self.window_avg())

    def _ratio(self, value: float | None) -> float:
        if value is None or self._floor is None or self._floor <= 0:
            return UNSTRESSED_RATIO
        return value / self._floor


def _publish_metrics(tracker: ReferenceQueryLoadTracker) -> None:
    floor = tracker.floor()
    if floor is not None:
        REFERENCE_QUERY_FLOOR_SECONDS.set(floor)
    window_min = tracker.window_min()
    if window_min is not None:
        REFERENCE_QUERY_WINDOW_MIN_SECONDS.set(window_min)
    REFERENCE_QUERY_STRESS_RATIO_MIN.set(tracker.stress_ratio_min())
    REFERENCE_QUERY_STRESS_RATIO_AVG.set(tracker.stress_ratio_avg())


# Process-global singleton fed by the database layer and read by the admission layer. Built
# with the default window; the startup wiring overrides it from settings.
reference_query_load_tracker = ReferenceQueryLoadTracker()
reference_query_load_tracker.set_observer(_publish_metrics)
