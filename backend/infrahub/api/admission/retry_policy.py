from __future__ import annotations

import time
from typing import Callable

# Persistence multipliers applied to the per-priority intensity base by how long load has been
# sustained. The base reflects the current intensity; these stretch a client's bounded retry
# budget across a longer real-time window when overload does not clear.
_SUSTAINED_MULTIPLIER_WARN = 2
_SUSTAINED_MULTIPLIER_HIGH = 3


class RetryAfterPolicy:
    """Computes the ``Retry-After`` hint for a shed request from load intensity and persistence.

    Two axes combine. Intensity is a per-priority tier (``1``/``2``/``3`` -> configured seconds)
    supplied by the caller — the same tiering that drives the graduated shed fraction, so a
    class's larger tolerance carries through to its retry hint. Persistence is how long this
    worker has continuously seen the database-stress ratio at or above the significant-load line;
    ratios below that line are a warm-up zone that never accrues sustained time. The per-tier base
    is multiplied by the persistence factor and clamped to a maximum.

    The current sustained-load duration is pushed to a registered observer (e.g. a metric gauge)
    after each observation, so the primitive itself stays free of any metrics dependency. State is
    per worker on a single event loop, so it takes no lock.
    """

    def __init__(
        self,
        *,
        level1_seconds: int = 1,
        level2_seconds: int = 5,
        level3_seconds: int = 10,
        max_seconds: int = 30,
        significant_load_ratio: float = 20.0,
        sustained_warn_seconds: float = 60.0,
        sustained_high_seconds: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._level_seconds = {1: level1_seconds, 2: level2_seconds, 3: level3_seconds}
        self._max_seconds = max_seconds
        self._significant_load_ratio = significant_load_ratio
        self._sustained_warn_seconds = sustained_warn_seconds
        self._sustained_high_seconds = sustained_high_seconds
        self._clock = clock
        # Monotonic timestamp when the current continuous overload episode began, or None while
        # the ratio is below the significant-load line.
        self._overload_since: float | None = None
        self._on_sustained_load: Callable[[float], None] | None = None

    def set_observer(self, on_change: Callable[[float], None] | None) -> None:
        """Register a callback invoked with the current sustained-load seconds after each observation.

        Lets an external sink (e.g. a metric gauge) track the episode without the policy depending
        on that sink.
        """
        self._on_sustained_load = on_change

    def observe(self, *, ratio: float) -> None:
        """Update the overload episode from the latest stress ratio and notify the observer.

        A ratio at or above the significant-load line starts the episode (if not already running);
        anything below resets it. Ratios in the warm-up zone therefore never accrue sustained time.
        """
        now = self._clock()
        if ratio >= self._significant_load_ratio:
            if self._overload_since is None:
                self._overload_since = now
        else:
            self._overload_since = None
        if self._on_sustained_load is not None:
            self._on_sustained_load(self._sustained_seconds(now))

    def retry_after(self, *, tier: int) -> int:
        """Seconds to advise a shed request to wait: the per-tier base scaled by sustained load.

        ``tier`` is the intensity level (``0`` floors to level 1, since any shed advises at least
        the level-1 wait). The result is clamped to the configured maximum.
        """
        base = self._level_seconds[min(max(tier, 1), 3)]
        multiplier = self._sustained_multiplier(self._sustained_seconds(self._clock()))
        return min(self._max_seconds, base * multiplier)

    def _sustained_seconds(self, now: float) -> float:
        if self._overload_since is None:
            return 0.0
        return now - self._overload_since

    def _sustained_multiplier(self, sustained: float) -> int:
        if sustained >= self._sustained_high_seconds:
            return _SUSTAINED_MULTIPLIER_HIGH
        if sustained >= self._sustained_warn_seconds:
            return _SUSTAINED_MULTIPLIER_WARN
        return 1
