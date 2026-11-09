from __future__ import annotations

import math
import time
from typing import Callable


class CoDelController:
    """Pure CoDel (Controlled Delay) state machine deciding admit vs shed from sojourn.

    One instance drives one priority class. The controller keys off how long requests
    wait for a slot (the sojourn) rather than a queue-length threshold, so it needs no
    per-deployment tuning. It is deterministic given its injected ``clock`` and performs
    no I/O.

    The control law: once sojourn stays above ``target`` continuously for a full
    ``interval`` the controller enters the dropping state and sheds on an inverse-square-root
    cadence (``interval / sqrt(count)``), so shedding accelerates the longer the overload
    persists. A single sample below ``target`` exits the dropping state, giving bounded
    recovery. A burst shorter than ``interval`` never reaches the drop condition.
    """

    def __init__(self, *, target: float, interval: float, clock: Callable[[], float] = time.monotonic) -> None:
        self._target = target
        self._interval = interval
        self._clock = clock

        self._dropping = False
        self._first_above_time: float | None = None
        self._drop_next = 0.0
        self._count = 0
        self._last_count = 0

    def _control_law(self, reference: float, count: int) -> float:
        return reference + self._interval / math.sqrt(count)

    def should_drop(self, sojourn: float) -> bool:
        """Decide whether the current request should be shed.

        Args:
            sojourn: Seconds the request waited to acquire a slot.

        Returns:
            ``True`` if the request should be shed, ``False`` if it should be admitted.

        """
        now = self._clock()

        if sojourn < self._target:
            # Below target: the excursion is over. Leave the dropping state immediately
            # (bounded recovery) and remember the cadence for a fast re-entry.
            if self._dropping:
                self._last_count = self._count
            self._first_above_time = None
            self._dropping = False
            return False

        ok_to_drop = False
        if self._first_above_time is None:
            # Start of an excursion above target; tolerate it for one full interval.
            self._first_above_time = now + self._interval
        elif now >= self._first_above_time:
            ok_to_drop = True

        if self._dropping:
            if now >= self._drop_next:
                self._count += 1
                self._drop_next = self._control_law(reference=self._drop_next, count=self._count)
                return True
            return False

        if ok_to_drop:
            # Enter the dropping state. If we dropped recently, resume near the prior
            # cadence for a faster reaction; otherwise start the schedule fresh.
            if (now - self._drop_next) < self._interval and self._last_count > 2:
                self._count = self._last_count - 2
            else:
                self._count = 1
            self._last_count = self._count
            self._dropping = True
            self._drop_next = self._control_law(reference=now, count=self._count)
            return True

        return False
