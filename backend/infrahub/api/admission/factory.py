from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.database.load_signal_registry import get_reference_query_load_tracker

from . import metrics
from .capacity import derive_max_concurrency
from .codel import CoDelController
from .controller import AdmissionController
from .priority import Priority
from .retry_policy import RetryAfterPolicy
from .slot_pool import PrioritySlotPool

if TYPE_CHECKING:
    from infrahub import config

    from .controller import AdmissionObserver
    from .retry_policy import RetryPolicyObserver
    from .slot_pool import SlotPoolObserver


def build_admission_controller(
    *,
    settings: config.Settings,
    admission_observers: list[AdmissionObserver],
    slot_pool_observers: list[SlotPoolObserver],
    retry_policy_observers: list[RetryPolicyObserver],
) -> AdmissionController:
    """Build the default admission controller from the given settings and observers.

    Keeps settings resolution out of ``AdmissionController`` itself: the decision logic stays
    settings-free and directly testable while this module owns the wiring of the defaults.

    Args:
        settings: Source of every tuning value the object graph needs.
        admission_observers: Sinks notified as each request is offered, admitted, or shed.
        slot_pool_observers: Sinks notified as a class's in-flight and waiter counts change.
        retry_policy_observers: Sinks notified with the current sustained-load duration.

    """
    max_concurrency = derive_max_concurrency(
        pool_size=settings.database.max_connection_pool_size,
        factor=settings.api.backpressure_max_concurrency_factor,
    )
    # Set the gauge wherever the controller is actually built, so it reflects the derived cap
    # in use rather than being frozen at some earlier import.
    metrics.MAX_CONCURRENCY.set(max_concurrency)
    slot_pool = PrioritySlotPool(max_concurrency=max_concurrency, observers=slot_pool_observers)

    # The database layer feeds this same instance, so the gate reads the signal the queries write.
    tracker = get_reference_query_load_tracker()

    base_backstop = settings.api.backpressure_backstop_max_waiters
    backstop_max_waiters = {
        Priority.HIGH: max(1, int(base_backstop * settings.api.backpressure_backstop_high_multiplier)),
        Priority.MEDIUM: base_backstop,
        Priority.LOW: max(1, int(base_backstop * settings.api.backpressure_backstop_low_multiplier)),
    }
    stress_thresholds = {
        Priority.HIGH: settings.api.backpressure_shed_high_stress_ratio,
        Priority.MEDIUM: settings.api.backpressure_shed_medium_stress_ratio,
        Priority.LOW: settings.api.backpressure_shed_low_stress_ratio,
    }
    # HIGH gets a larger effective target so it sheds last; MEDIUM and LOW share the base target.
    codel = {
        Priority.HIGH: CoDelController(
            target=settings.api.backpressure_codel_target_seconds * settings.api.backpressure_high_target_multiplier,
            interval=settings.api.backpressure_codel_interval_seconds,
        ),
        Priority.MEDIUM: CoDelController(
            target=settings.api.backpressure_codel_target_seconds,
            interval=settings.api.backpressure_codel_interval_seconds,
        ),
        Priority.LOW: CoDelController(
            target=settings.api.backpressure_codel_target_seconds,
            interval=settings.api.backpressure_codel_interval_seconds,
        ),
    }
    retry_policy = RetryAfterPolicy(
        observers=retry_policy_observers,
        level1_seconds=settings.api.backpressure_retry_after_level1_seconds,
        level2_seconds=settings.api.backpressure_retry_after_level2_seconds,
        level3_seconds=settings.api.backpressure_retry_after_level3_seconds,
        max_seconds=settings.api.backpressure_retry_after_max_seconds,
        significant_load_ratio=settings.api.backpressure_significant_load_stress_ratio,
        sustained_warn_seconds=settings.api.backpressure_sustained_load_warn_seconds,
        sustained_high_seconds=settings.api.backpressure_sustained_load_high_seconds,
    )
    return AdmissionController(
        slot_pool=slot_pool,
        codel_priority_map=codel,
        backstop_max_waiters=backstop_max_waiters,
        stress_signal=tracker,
        stress_thresholds=stress_thresholds,
        stress_min_samples=settings.api.backpressure_stress_min_samples,
        retry_policy=retry_policy,
        observers=admission_observers,
    )
