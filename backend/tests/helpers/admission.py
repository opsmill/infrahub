"""Admission-layer fixtures shared by the component tests that gate a bare FastAPI app."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from infrahub.api.admission.codel import CoDelController
from infrahub.api.admission.controller import AdmissionController
from infrahub.api.admission.middleware import AdmissionMiddleware
from infrahub.api.admission.observers import AdmissionMetricsObserver, SlotPoolMetricsObserver
from infrahub.api.admission.priority import Priority
from infrahub.api.admission.retry_policy import RetryAfterPolicy
from infrahub.api.admission.slot_pool import PrioritySlotPool

if TYPE_CHECKING:
    from collections.abc import Callable

    from fastapi import FastAPI


class FakeLoadSignal:
    """Hand-set database-stress signal for driving the admission decision deterministically."""

    def __init__(self, *, ratio: float, samples: int) -> None:
        self._ratio = ratio
        self._samples = samples

    def stress_ratio_median(self) -> float:
        return self._ratio

    def sample_count(self) -> int:
        return self._samples


# A ratio of 1.0 (database at its best) is below every threshold, so the stress trigger stays
# quiet and never sheds — leaving CoDel and the backstop as the only shed mechanisms.
UNSTRESSED = FakeLoadSignal(ratio=1.0, samples=1_000_000)

# Realistic per-class thresholds; the quiet signal above never reaches them, so tests built on it
# exercise CoDel/backstop shedding in isolation. The stress trigger and its tiering are covered by
# the dedicated controller unit test.
THRESHOLDS = {Priority.HIGH: 100.0, Priority.MEDIUM: 10.0, Priority.LOW: 5.0}


def codel_controllers(
    *, target: float, interval: float, high_target_multiplier: float, clock: Callable[[], float] = time.monotonic
) -> dict[Priority, CoDelController]:
    """Per-class CoDel controllers, HIGH given a larger effective target so it sheds last."""
    return {
        Priority.HIGH: CoDelController(target=target * high_target_multiplier, interval=interval, clock=clock),
        Priority.MEDIUM: CoDelController(target=target, interval=interval, clock=clock),
        Priority.LOW: CoDelController(target=target, interval=interval, clock=clock),
    }


def install_admission(app: FastAPI, controller: AdmissionController, *, enabled: bool = True) -> None:
    """Publish the controller/kill-switch on app.state (as the startup lifespan does) and gate the app.

    The middleware reads both from app.state per request; setting them here mirrors production
    startup without a live server.
    """
    app.state.admission_controller = controller
    app.state.admission_enabled = enabled
    app.add_middleware(AdmissionMiddleware)


def shed_everything_controller() -> AdmissionController:
    """Controller with no slots and no waiter budget: every admitted attempt is shed."""
    return AdmissionController(
        slot_pool=PrioritySlotPool(max_concurrency=0, observers=[SlotPoolMetricsObserver()]),
        codel_priority_map=codel_controllers(target=0.005, interval=0.1, high_target_multiplier=4.0),
        backstop_max_waiters=dict.fromkeys(Priority, 0),
        stress_signal=UNSTRESSED,
        stress_thresholds=THRESHOLDS,
        stress_min_samples=0,
        retry_policy=RetryAfterPolicy(observers=[]),
        observers=[AdmissionMetricsObserver()],
    )
