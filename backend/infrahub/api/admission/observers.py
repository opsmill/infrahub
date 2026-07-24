from __future__ import annotations

from typing import TYPE_CHECKING

from . import metrics

if TYPE_CHECKING:
    from .priority import Priority


class SlotPoolMetricsObserver:
    """Mirrors a class's live in-flight and waiter counts onto the Prometheus gauges."""

    def on_counts_changed(self, priority: Priority, *, in_flight: int, waiters: int) -> None:
        metrics.IN_FLIGHT.labels(priority=priority.label).set(in_flight)
        metrics.WAITERS.labels(priority=priority.label).set(waiters)


class SustainedLoadMetricsObserver:
    """Mirrors the current sustained-load duration onto the Prometheus gauge."""

    def on_sustained_load(self, *, sustained_seconds: float) -> None:
        metrics.SUSTAINED_LOAD_SECONDS.set(sustained_seconds)
