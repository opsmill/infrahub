from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Literal

from infrahub.database.load_signal import get_reference_query_load_tracker

from . import metrics
from .capacity import derive_max_concurrency
from .codel import CoDelController
from .priority import Priority
from .slot_pool import PrioritySlotPool

if TYPE_CHECKING:
    from infrahub import config
    from infrahub.database.load_signal import LoadSignal

    from .slot_pool import Acquisition

# Fraction of a stressed class's requests to shed, escalating with how far the stress ratio has
# climbed past that class's trigger (its threshold). The same schedule applies to every class;
# only the trigger differs, so a graduated response replaces shedding the whole class at once.
_SHED_FRACTION_MILD = 0.20  # within [1x, 2x) of the trigger
_SHED_FRACTION_MODERATE = 0.50  # within [2x, 5x) of the trigger
_SHED_FRACTION_SEVERE = 0.80  # at or beyond 5x the trigger


def stress_shed_fraction(*, ratio: float, threshold: float) -> float:
    """Fraction of requests to shed for a class given the stress ratio and the class's trigger.

    Returns ``0.0`` below the trigger, then steps up as the ratio climbs to 2x, 5x, and beyond.
    """
    if threshold <= 0:
        return 0.0
    multiple = ratio / threshold
    if multiple < 1.0:
        return 0.0
    if multiple < 2.0:
        return _SHED_FRACTION_MILD
    if multiple < 5.0:
        return _SHED_FRACTION_MODERATE
    return _SHED_FRACTION_SEVERE


@dataclass(frozen=True)
class Admitted:
    """Decision to run the request; carries the held slot."""

    acquisition: Acquisition


@dataclass(frozen=True)
class Rejected:
    """Decision to shed the request, with the reason and a Retry-After hint (seconds)."""

    reason: Literal["stress", "codel", "backstop"]
    retry_after: int


AdmissionDecision = Admitted | Rejected


class AdmissionController:
    """Turns a priority class into an admit/shed decision.

    Composes the shared slot pool, one CoDel controller per priority class, a per-class
    waiter backstop, and a database-stress signal. All tuning is passed in, so the class
    carries no dependency on global settings and is directly testable; the module-level
    factory wires the defaults.

    Two independent signals shed a request. Database stress (how much slower the reference query
    is than its all-time best) sheds a growing fraction of a class as the ratio climbs past that
    class's threshold — tiered so LOW sheds first, MEDIUM next, and HIGH only under extreme load,
    and graduated so a class is never shed wholesale the instant its trigger is crossed. Stress is
    evaluated before the request queues for a slot, so a stressed request is shed fast without
    waiting behind a saturated pool. CoDel sheds when a class's slot-wait (sojourn) overruns; it
    keys off the measured sojourn, so it only runs once a slot is held — a request shed by stress
    never reaches it. The backstop is a third, unconditional per-class memory-safety cap that
    bounds the waiter queue regardless of either signal.
    """

    def __init__(
        self,
        *,
        slot_pool: PrioritySlotPool,
        codel: dict[Priority, CoDelController],
        backstop_max_waiters: dict[Priority, int],
        stress_signal: LoadSignal,
        stress_thresholds: dict[Priority, float],
        stress_min_samples: int,
        retry_after: int,
        rng: Callable[[], float] = random.random,
    ) -> None:
        self._slot_pool = slot_pool
        # Publish the live gauges straight from the pool's own state transitions, so a class's
        # waiter count is reflected the moment a request enqueues. The sink is a plain function
        # fed the counts by the pool, so nothing reads back into the pool.
        self._slot_pool.set_observer(_publish_slot_metrics)
        self._backstop_max_waiters = backstop_max_waiters
        self._stress_signal = stress_signal
        self._stress_thresholds = stress_thresholds
        self._stress_min_samples = stress_min_samples
        self._retry_after = retry_after
        # Source of the [0, 1) draw used to shed a fraction of a stressed class's requests.
        self._rng = rng
        self._codel = codel

    async def admit(self, *, priority: Priority) -> AdmissionDecision:
        """Decide whether to admit or shed a request of the given priority.

        Args:
            priority: The resolved priority class of the request.

        Returns:
            ``Admitted`` carrying the held slot, or ``Rejected`` with the shed reason.

        """
        metrics.OFFERED_TOTAL.labels(priority=priority.label).inc()

        if self._slot_pool.waiters(priority=priority) >= self._backstop_max_waiters[priority]:
            metrics.REJECTED_TOTAL.labels(priority=priority.label, reason="backstop").inc()
            return Rejected(reason="backstop", retry_after=self._retry_after)

        # Database stress is evaluated before the request queues for a slot: a stressed class sheds
        # a random fraction of its requests, and a shed one gets its fast 429 without waiting behind
        # a saturated pool or consuming waiter capacity. CoDel keys off the measured sojourn, so it
        # can only run once a slot is held — a request shed here never reaches it.
        if self._stress_should_shed(priority=priority):
            metrics.REJECTED_TOTAL.labels(priority=priority.label, reason="stress").inc()
            return Rejected(reason="stress", retry_after=self._retry_after)

        acquisition = await self._slot_pool.acquire(priority=priority)
        # Once a slot is held, any exception before returning Admitted would strand it (the
        # caller only releases what it receives), so guard the whole window and release on error.
        try:
            metrics.SOJOURN_SECONDS.labels(priority=priority.label).observe(acquisition.sojourn)

            if self._codel[priority].should_drop(sojourn=acquisition.sojourn):
                self._slot_pool.release(acquisition=acquisition)
                metrics.REJECTED_TOTAL.labels(priority=priority.label, reason="codel").inc()
                return Rejected(reason="codel", retry_after=self._retry_after)

            metrics.ADMITTED_TOTAL.labels(priority=priority.label).inc()
            return Admitted(acquisition=acquisition)
        except Exception:
            self._slot_pool.release(acquisition=acquisition)
            raise

    def _stress_should_shed(self, *, priority: Priority) -> bool:
        """Whether database stress sheds this request: a random draw against the class's fraction."""
        shed_fraction = self._stress_shed_fraction(priority=priority)
        return shed_fraction > 0.0 and self._rng() < shed_fraction

    def _stress_shed_fraction(self, *, priority: Priority) -> float:
        # Until the window holds enough samples, the floor is unreliable (a cold or outlier
        # floor would distort the ratio), so the stress signal sheds nothing yet.
        if self._stress_signal.sample_count() < self._stress_min_samples:
            return 0.0
        return stress_shed_fraction(
            ratio=self._stress_signal.stress_ratio_median(), threshold=self._stress_thresholds[priority]
        )

    def release(self, *, acquisition: Acquisition) -> None:
        """Return a served request's slot; the pool observer refreshes the live gauges.

        The release flows through the pool, whose observer drives ``in_flight``/``waiters``
        back down, so a finished request is reflected immediately rather than lingering
        until the next admit.
        """
        self._slot_pool.release(acquisition=acquisition)


def _publish_slot_metrics(priority: Priority, *, in_flight: int, waiters: int) -> None:
    """Pool observer sink: mirror a class's live in-flight and waiter counts onto the gauges."""
    metrics.IN_FLIGHT.labels(priority=priority.label).set(in_flight)
    metrics.WAITERS.labels(priority=priority.label).set(waiters)


def build_admission_controller(settings: config.Settings) -> AdmissionController:
    """Build the default admission controller from the given settings.

    Keeps settings resolution out of ``AdmissionController`` itself: the class stays
    settings-free and testable while this factory owns the wiring of the defaults.
    """
    max_concurrency = derive_max_concurrency(
        pool_size=settings.database.max_connection_pool_size,
        factor=settings.api.backpressure_max_concurrency_factor,
    )
    # Set the gauge wherever the controller is actually built, so it reflects the derived cap
    # in use rather than being frozen at some earlier import.
    metrics.MAX_CONCURRENCY.set(max_concurrency)
    slot_pool = PrioritySlotPool(max_concurrency=max_concurrency)

    # The stress window lives on the shared tracker; apply the configured length here, where
    # settings are available, rather than at the tracker's construction.
    tracker = get_reference_query_load_tracker()
    tracker.window_seconds = settings.api.backpressure_stress_window_seconds

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
    return AdmissionController(
        slot_pool=slot_pool,
        codel=codel,
        backstop_max_waiters=backstop_max_waiters,
        stress_signal=tracker,
        stress_thresholds=stress_thresholds,
        stress_min_samples=settings.api.backpressure_stress_min_samples,
        retry_after=settings.api.backpressure_retry_after_seconds,
    )
