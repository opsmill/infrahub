from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Literal

from infrahub import config
from infrahub.database.load_signal import reference_query_load_tracker

from . import metrics
from .capacity import derive_max_concurrency
from .codel import CoDelController
from .priority import Priority
from .slot_pool import PrioritySlotPool

if TYPE_CHECKING:
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

    Two independent signals shed a request; neither gates the other. Database stress (how much
    slower the reference query is than its all-time best) sheds a growing fraction of a class as
    the ratio climbs past that class's threshold — tiered so LOW sheds first, MEDIUM next, and
    HIGH only under extreme load, and graduated so a class is never shed wholesale the instant
    its trigger is crossed. CoDel sheds when a class's slot-wait (sojourn) overruns, independently
    of database stress. Either firing sheds the request; when both fire the shed is attributed to
    stress. The backstop is a third, unconditional per-class memory-safety cap that bounds the
    waiter queue regardless of either signal.
    """

    def __init__(
        self,
        *,
        slot_pool: PrioritySlotPool,
        target: float,
        interval: float,
        high_target_multiplier: float,
        backstop_max_waiters: dict[Priority, int],
        stress_signal: LoadSignal,
        stress_thresholds: dict[Priority, float],
        stress_min_samples: int,
        retry_after: int,
        clock: Callable[[], float] = time.monotonic,
        rng: Callable[[], float] = random.random,
    ) -> None:
        self._slot_pool = slot_pool
        # Drive the live gauges from the pool's own state transitions, so a class's waiter
        # count is reflected the moment a request enqueues — not only once some other
        # request is admitted or released.
        self._slot_pool.set_observer(self._sync_gauges)
        self._backstop_max_waiters = backstop_max_waiters
        self._stress_signal = stress_signal
        self._stress_thresholds = stress_thresholds
        self._stress_min_samples = stress_min_samples
        self._retry_after = retry_after
        # Source of the [0, 1) draw used to shed a fraction of a stressed class's requests.
        self._rng = rng
        # HIGH gets a larger effective target so it sheds last; MEDIUM and LOW share the base target.
        self._codel: dict[Priority, CoDelController] = {
            Priority.HIGH: CoDelController(target=target * high_target_multiplier, interval=interval, clock=clock),
            Priority.MEDIUM: CoDelController(target=target, interval=interval, clock=clock),
            Priority.LOW: CoDelController(target=target, interval=interval, clock=clock),
        }

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

        acquisition = await self._slot_pool.acquire(priority=priority)
        # Once a slot is held, any exception before returning Admitted would strand it (the
        # caller only releases what it receives), so guard the whole window and release on error.
        try:
            metrics.SOJOURN_SECONDS.labels(priority=priority.label).observe(acquisition.sojourn)

            # Two independent shed signals, evaluated every request so CoDel keeps observing
            # sojourn continuously. Database stress sheds a fraction of the class (a random draw
            # against the escalating schedule); CoDel sheds on sojourn overrun. Stress is
            # attributed first when both fire, so the stress dimension stays visible.
            shed_fraction = self._stress_shed_fraction(priority=priority)
            stressed = shed_fraction > 0.0 and self._rng() < shed_fraction
            codel_drop = self._codel[priority].should_drop(sojourn=acquisition.sojourn)
            shed_reason: Literal["stress", "codel"] | None
            if stressed:
                shed_reason = "stress"
            elif codel_drop:
                shed_reason = "codel"
            else:
                shed_reason = None

            if shed_reason is not None:
                acquisition.release()
                metrics.REJECTED_TOTAL.labels(priority=priority.label, reason=shed_reason).inc()
                return Rejected(reason=shed_reason, retry_after=self._retry_after)

            metrics.ADMITTED_TOTAL.labels(priority=priority.label).inc()
            return Admitted(acquisition=acquisition)
        except Exception:
            acquisition.release()
            raise

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
        acquisition.release()

    def _sync_gauges(self, priority: Priority) -> None:
        metrics.IN_FLIGHT.labels(priority=priority.label).set(self._slot_pool.in_flight(priority=priority))
        metrics.WAITERS.labels(priority=priority.label).set(self._slot_pool.waiters(priority=priority))


def build_admission_controller() -> AdmissionController:
    """Build the default admission controller from global settings.

    Keeps settings resolution out of ``AdmissionController`` itself: the class stays
    settings-free and testable while this factory owns the wiring of the defaults.
    """
    settings = config.SETTINGS
    max_concurrency = derive_max_concurrency(
        pool_size=settings.database.max_connection_pool_size,
        factor=settings.api.backpressure_max_concurrency_factor,
    )
    # Set the gauge wherever the controller is actually built, so it reflects the derived cap
    # in use rather than being frozen at some earlier import.
    metrics.MAX_CONCURRENCY.set(max_concurrency)
    slot_pool = PrioritySlotPool(max_concurrency=max_concurrency)

    # The stress window lives on the shared tracker; apply the configured length here, where
    # settings are available, rather than at the tracker's import.
    reference_query_load_tracker.window_seconds = settings.api.backpressure_stress_window_seconds

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
    return AdmissionController(
        slot_pool=slot_pool,
        target=settings.api.backpressure_codel_target_seconds,
        interval=settings.api.backpressure_codel_interval_seconds,
        high_target_multiplier=settings.api.backpressure_high_target_multiplier,
        backstop_max_waiters=backstop_max_waiters,
        stress_signal=reference_query_load_tracker,
        stress_thresholds=stress_thresholds,
        stress_min_samples=settings.api.backpressure_stress_min_samples,
        retry_after=settings.api.backpressure_retry_after_seconds,
    )
