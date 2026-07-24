from __future__ import annotations

from infrahub.api.admission.priority import Priority


class FakeClock:
    """Manually advanced monotonic clock so admission timing is deterministic in tests."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class RecordingSlotPoolObserver:
    """Slot-pool sink that keeps the counts last pushed for each priority class."""

    def __init__(self) -> None:
        self.in_flight: dict[Priority, int] = dict.fromkeys(Priority, 0)
        self.waiters: dict[Priority, int] = dict.fromkeys(Priority, 0)
        self.calls = 0

    def on_counts_changed(self, priority: Priority, *, in_flight: int, waiters: int) -> None:
        self.in_flight[priority] = in_flight
        self.waiters[priority] = waiters
        self.calls += 1


class FailingSlotPoolObserver:
    """Slot-pool sink that raises on every transition, to prove failures stay contained."""

    def on_counts_changed(self, priority: Priority, *, in_flight: int, waiters: int) -> None:
        raise RuntimeError("observer blew up")
