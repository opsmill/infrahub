from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Literal

from infrahub import config

from . import metrics
from .capacity import derive_max_concurrency
from .codel import CoDelController
from .priority import Priority
from .slot_pool import PrioritySlotPool

if TYPE_CHECKING:
    from .slot_pool import Acquisition


@dataclass(frozen=True)
class Admitted:
    """Decision to run the request; carries the held slot."""

    acquisition: Acquisition


@dataclass(frozen=True)
class Rejected:
    """Decision to shed the request, with the reason and a Retry-After hint (seconds)."""

    reason: Literal["codel", "backstop"]
    retry_after: int


AdmissionDecision = Admitted | Rejected


class AdmissionController:
    """Turns a priority class into an admit/shed decision.

    Composes the shared slot pool, one CoDel controller per priority class, and a hard
    waiter backstop. All tuning is passed in, so the class carries no dependency on global
    settings and is directly testable; the module-level factory wires the defaults.
    """

    def __init__(
        self,
        *,
        slot_pool: PrioritySlotPool,
        target: float,
        interval: float,
        high_target_multiplier: float,
        backstop_max_waiters: int,
        retry_after: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._slot_pool = slot_pool
        self._backstop_max_waiters = backstop_max_waiters
        self._retry_after = retry_after
        # HIGH gets a larger effective target so it sheds last; NORMAL and LOW share the base target.
        self._codel: dict[Priority, CoDelController] = {
            Priority.HIGH: CoDelController(target=target * high_target_multiplier, interval=interval, clock=clock),
            Priority.NORMAL: CoDelController(target=target, interval=interval, clock=clock),
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

        if self._slot_pool.waiters(priority=priority) >= self._backstop_max_waiters:
            metrics.REJECTED_TOTAL.labels(priority=priority.label, reason="backstop").inc()
            return Rejected(reason="backstop", retry_after=self._retry_after)

        acquisition = await self._slot_pool.acquire(priority=priority)
        self._sync_gauges(priority=priority)
        metrics.SOJOURN_SECONDS.labels(priority=priority.label).observe(acquisition.sojourn)

        if self._codel[priority].should_drop(sojourn=acquisition.sojourn):
            acquisition.release()
            self._sync_gauges(priority=priority)
            metrics.REJECTED_TOTAL.labels(priority=priority.label, reason="codel").inc()
            return Rejected(reason="codel", retry_after=self._retry_after)

        metrics.ADMITTED_TOTAL.labels(priority=priority.label).inc()
        return Admitted(acquisition=acquisition)

    def release(self, *, acquisition: Acquisition) -> None:
        """Return a served request's slot and refresh the live gauges for its class.

        Releasing through the controller (rather than the acquisition directly) keeps the
        gauge sync co-located with every slot state change, so ``in_flight`` drops back as
        soon as a request finishes instead of lingering until the next admit.
        """
        acquisition.release()
        self._sync_gauges(priority=acquisition.priority)

    def _sync_gauges(self, *, priority: Priority) -> None:
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
    slot_pool = PrioritySlotPool(max_concurrency=max_concurrency)
    return AdmissionController(
        slot_pool=slot_pool,
        target=settings.api.backpressure_codel_target_seconds,
        interval=settings.api.backpressure_codel_interval_seconds,
        high_target_multiplier=settings.api.backpressure_high_target_multiplier,
        backstop_max_waiters=settings.api.backpressure_backstop_max_waiters,
        retry_after=settings.api.backpressure_retry_after_seconds,
    )
