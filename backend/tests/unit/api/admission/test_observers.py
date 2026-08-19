from __future__ import annotations

from infrahub.api.admission import metrics
from infrahub.api.admission.constants import RejectionReason
from infrahub.api.admission.observers import AdmissionMetricsObserver, SustainedLoadMetricsObserver
from infrahub.api.admission.priority import Priority


def _rejected(*, priority: str, reason: str) -> float:
    return metrics.REJECTED_TOTAL.labels(priority=priority, reason=reason)._value.get()


def test_rejection_reason_labels_the_counter_by_its_value() -> None:
    observer = AdmissionMetricsObserver()
    # The reason reaches the gauge as an enum member but is scraped as a label string, so a
    # plain-string lookup has to find the very same counter the observer incremented.
    before = _rejected(priority="low", reason="backstop")

    observer.on_rejected(priority=Priority.LOW, reason=RejectionReason.BACKSTOP)

    assert _rejected(priority="low", reason="backstop") - before == 1.0


def test_each_reason_increments_its_own_counter() -> None:
    observer = AdmissionMetricsObserver()
    before = {reason: _rejected(priority="medium", reason=reason) for reason in RejectionReason}

    for reason in RejectionReason:
        observer.on_rejected(priority=Priority.MEDIUM, reason=reason)

    after = {reason: _rejected(priority="medium", reason=reason) for reason in RejectionReason}
    assert {reason: after[reason] - before[reason] for reason in RejectionReason} == dict.fromkeys(RejectionReason, 1.0)


def test_sustained_load_reaches_its_gauge() -> None:
    observer = SustainedLoadMetricsObserver()

    observer.on_sustained_load(sustained_seconds=45.0)
    assert metrics.SUSTAINED_LOAD_SECONDS._value.get() == 45.0

    # A cleared episode reports zero, so the gauge has to fall back rather than latch its peak.
    observer.on_sustained_load(sustained_seconds=0.0)
    assert metrics.SUSTAINED_LOAD_SECONDS._value.get() == 0.0
