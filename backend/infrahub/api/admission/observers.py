from __future__ import annotations

from typing import TYPE_CHECKING

from . import metrics

if TYPE_CHECKING:
    from .constants import RejectionReason
    from .priority import Priority


class AdmissionMetricsObserver:
    """Mirrors each admission decision onto the Prometheus counters and the sojourn histogram."""

    def on_offered(self, *, priority: Priority) -> None:
        metrics.OFFERED_TOTAL.labels(priority=priority.label).inc()

    def on_admitted(self, *, priority: Priority) -> None:
        metrics.ADMITTED_TOTAL.labels(priority=priority.label).inc()

    def on_rejected(self, *, priority: Priority, reason: RejectionReason) -> None:
        metrics.REJECTED_TOTAL.labels(priority=priority.label, reason=reason).inc()

    def on_sojourn(self, *, priority: Priority, seconds: float) -> None:
        metrics.SOJOURN_SECONDS.labels(priority=priority.label).observe(seconds)


class SlotPoolMetricsObserver:
    """Mirrors a class's live in-flight and waiter counts onto the Prometheus gauges."""

    def on_counts_changed(self, priority: Priority, *, in_flight: int, waiters: int) -> None:
        metrics.IN_FLIGHT.labels(priority=priority.label).set(in_flight)
        metrics.WAITERS.labels(priority=priority.label).set(waiters)


class SustainedLoadMetricsObserver:
    """Mirrors the current sustained-load duration onto the Prometheus gauge."""

    def on_sustained_load(self, *, sustained_seconds: float) -> None:
        metrics.SUSTAINED_LOAD_SECONDS.set(sustained_seconds)
