from __future__ import annotations

import random
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Generator, Protocol

from infrahub.database.load_signal import UNSTRESSED_RATIO
from infrahub.log import get_logger

from .constants import RejectionReason

if TYPE_CHECKING:
    from infrahub.database.load_signal import LoadSignal

    from .codel import CoDelController
    from .priority import Priority
    from .retry_policy import RetryAfterPolicy
    from .slot_pool import Acquisition, PrioritySlotPool

log = get_logger()

# Backstop shedding (waiter queue saturated) is unambiguous overload, so its retry-after hint
# always uses the top intensity tier regardless of the current stress ratio.
_BACKSTOP_TIER = 3

# Fraction of a stressed class's requests to shed at each tier. The same schedule applies to every
# class; only the trigger differs, so a graduated response replaces shedding the whole class at
# once. The tiers are shared with the adaptive retry-after, so a class's escalation is expressed
# once and both the drop percentage and the retry hint move together.
_SHED_FRACTION_BY_TIER = {0: 0.0, 1: 0.20, 2: 0.50, 3: 0.80}


def stress_tier(*, ratio: float, threshold: float) -> int:
    """Severity tier of a stress ratio against a class's trigger.

    Returns ``0`` below the trigger, then ``1``/``2``/``3`` (mild/moderate/severe) as the ratio
    climbs past ``1x``/``2x``/``5x`` of the trigger.
    """
    if threshold <= 0:
        return 0
    multiple = ratio / threshold
    if multiple < 1.0:
        return 0
    if multiple < 2.0:
        return 1
    if multiple < 5.0:
        return 2
    return 3


def stress_shed_fraction(*, tier: int) -> float:
    """Fraction of a class's requests to shed at a given severity tier."""
    return _SHED_FRACTION_BY_TIER[tier]


@dataclass(frozen=True)
class Admitted:
    """Decision to run the request; carries the held slot."""

    acquisition: Acquisition


@dataclass(frozen=True)
class Rejected:
    """Decision to shed the request, with the reason and a Retry-After hint (seconds)."""

    reason: RejectionReason
    retry_after: int


AdmissionDecision = Admitted | Rejected


@contextmanager
def _contained_observer_failure() -> Generator[None]:
    """Log whatever one observer raises instead of letting it reach the admission path."""
    try:
        yield
    except Exception:
        log.warning("admission observer raised; continuing", exc_info=True)


class AdmissionObserver(Protocol):
    """Sink notified as a request moves through the admission decision."""

    def on_offered(self, *, priority: Priority) -> None: ...

    def on_admitted(self, *, priority: Priority) -> None: ...

    def on_rejected(self, *, priority: Priority, reason: RejectionReason) -> None: ...

    def on_sojourn(self, *, priority: Priority, seconds: float) -> None: ...


class AdmissionController:
    """Turns a priority class into an admit/shed decision.

    Composes the shared slot pool, one CoDel controller per priority class, a per-class
    waiter backstop, and a database-stress signal. Every collaborator and tuning value is
    injected, so the class carries no dependency on global settings and is directly testable.

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
        codel_priority_map: dict[Priority, CoDelController],
        backstop_max_waiters: dict[Priority, int],
        stress_signal: LoadSignal,
        stress_thresholds: dict[Priority, float],
        stress_min_samples: int,
        retry_policy: RetryAfterPolicy,
        observers: list[AdmissionObserver],
        rng: Callable[[], float] = random.random,
    ) -> None:
        self._slot_pool = slot_pool
        self._retry_policy = retry_policy
        self._observers = observers
        self._backstop_max_waiters = backstop_max_waiters
        self._stress_signal = stress_signal
        self._stress_thresholds = stress_thresholds
        self._stress_min_samples = stress_min_samples
        # Source of the [0, 1) draw used to shed a fraction of a stressed class's requests.
        self._rng = rng
        self._codel_priority_map = codel_priority_map

    async def admit(self, *, priority: Priority) -> AdmissionDecision:
        """Decide whether to admit or shed a request of the given priority.

        Args:
            priority: The resolved priority class of the request.

        Returns:
            ``Admitted`` carrying the held slot, or ``Rejected`` with the shed reason.

        """
        self._observe_offered(priority=priority)

        # The stress ratio is the shared server-load proxy: it drives the graduated shed decision
        # and, via the retry policy, both the adaptive Retry-After and the sustained-load clock.
        # Sample it once and let the policy track how long load has persisted.
        ratio = self._current_stress_ratio()
        self._retry_policy.observe(ratio=ratio)
        tier = stress_tier(ratio=ratio, threshold=self._stress_thresholds[priority])

        if self._slot_pool.waiters(priority=priority) >= self._backstop_max_waiters[priority]:
            self._observe_rejected(priority=priority, reason=RejectionReason.BACKSTOP)
            # A saturated waiter queue is unambiguous overload, so the hint uses the top tier.
            return Rejected(
                reason=RejectionReason.BACKSTOP, retry_after=self._retry_policy.retry_after(tier=_BACKSTOP_TIER)
            )

        # Database stress is evaluated before the request queues for a slot: a stressed class sheds
        # a random fraction of its requests, and a shed one gets its fast 429 without waiting behind
        # a saturated pool or consuming waiter capacity. CoDel keys off the measured sojourn, so it
        # can only run once a slot is held — a request shed here never reaches it.
        if tier >= 1 and self._rng() < stress_shed_fraction(tier=tier):
            self._observe_rejected(priority=priority, reason=RejectionReason.STRESS)
            return Rejected(reason=RejectionReason.STRESS, retry_after=self._retry_policy.retry_after(tier=tier))

        acquisition = await self._slot_pool.acquire(priority=priority)
        # Once a slot is held, any exception before returning Admitted would strand it (the
        # caller only releases what it receives), so guard the whole window and release on error.
        try:
            self._observe_sojourn(priority=priority, seconds=acquisition.sojourn)

            if self._codel_priority_map[priority].should_drop(sojourn=acquisition.sojourn):
                self._slot_pool.release(acquisition=acquisition)
                self._observe_rejected(priority=priority, reason=RejectionReason.CODEL)
                return Rejected(reason=RejectionReason.CODEL, retry_after=self._retry_policy.retry_after(tier=tier))

            self._observe_admitted(priority=priority)
            return Admitted(acquisition=acquisition)
        except Exception:
            self._slot_pool.release(acquisition=acquisition)
            raise

    def _observe_offered(self, *, priority: Priority) -> None:
        for observer in self._observers:
            with _contained_observer_failure():
                observer.on_offered(priority=priority)

    def _observe_admitted(self, *, priority: Priority) -> None:
        for observer in self._observers:
            with _contained_observer_failure():
                observer.on_admitted(priority=priority)

    def _observe_rejected(self, *, priority: Priority, reason: RejectionReason) -> None:
        for observer in self._observers:
            with _contained_observer_failure():
                observer.on_rejected(priority=priority, reason=reason)

    def _observe_sojourn(self, *, priority: Priority, seconds: float) -> None:
        for observer in self._observers:
            with _contained_observer_failure():
                observer.on_sojourn(priority=priority, seconds=seconds)

    def _current_stress_ratio(self) -> float:
        # Below the sample floor the ratio is unreliable (a cold or outlier floor would distort
        # it), so the signal reads as unstressed — matching the shed gate, which also stays quiet
        # until the window holds enough samples.
        if self._stress_signal.sample_count() < self._stress_min_samples:
            return UNSTRESSED_RATIO
        return self._stress_signal.stress_ratio_median()

    def release(self, *, acquisition: Acquisition) -> None:
        """Return a served request's slot; the pool's observers refresh the live gauges.

        The release flows through the pool, whose observers drive ``in_flight``/``waiters``
        back down, so a finished request is reflected immediately rather than lingering
        until the next admit.
        """
        self._slot_pool.release(acquisition=acquisition)
