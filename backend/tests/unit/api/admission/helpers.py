from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.api.admission.priority import Priority

if TYPE_CHECKING:
    from infrahub.api.admission.constants import RejectionReason


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


class RecordingAdmissionObserver:
    """Admission sink that keeps every event pushed to it, in order."""

    def __init__(self) -> None:
        self.events: list[tuple[str, Priority]] = []
        self.sojourns: list[float] = []

    def on_offered(self, *, priority: Priority) -> None:
        self.events.append(("offered", priority))

    def on_admitted(self, *, priority: Priority) -> None:
        self.events.append(("admitted", priority))

    def on_rejected(self, *, priority: Priority, reason: RejectionReason) -> None:
        self.events.append((f"rejected:{reason}", priority))

    def on_sojourn(self, *, priority: Priority, seconds: float) -> None:
        self.events.append(("sojourn", priority))
        self.sojourns.append(seconds)


class FailingAdmissionObserver:
    """Admission sink that raises on every event, to prove failures stay contained."""

    def on_offered(self, *, priority: Priority) -> None:
        raise RuntimeError("observer blew up")

    def on_admitted(self, *, priority: Priority) -> None:
        raise RuntimeError("observer blew up")

    def on_rejected(self, *, priority: Priority, reason: RejectionReason) -> None:
        raise RuntimeError("observer blew up")

    def on_sojourn(self, *, priority: Priority, seconds: float) -> None:
        raise RuntimeError("observer blew up")


class FailingSlotPoolObserver:
    """Slot-pool sink that raises on every transition, to prove failures stay contained."""

    def on_counts_changed(self, priority: Priority, *, in_flight: int, waiters: int) -> None:
        raise RuntimeError("observer blew up")
