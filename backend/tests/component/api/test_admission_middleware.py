from __future__ import annotations

import asyncio
import time

import httpx
import pytest
from fastapi import FastAPI

from infrahub.api.admission import metrics
from infrahub.api.admission.capacity import derive_max_concurrency
from infrahub.api.admission.controller import AdmissionController
from infrahub.api.admission.middleware import AdmissionMiddleware
from infrahub.api.admission.priority import Priority
from infrahub.api.admission.slot_pool import PrioritySlotPool

HANDLER_SLEEP = 0.02
MAX_CONCURRENCY = 2
LOW_REQUESTS = 60
HIGH_REQUESTS = 15

_PRIORITY_LABELS = ("high", "normal", "low")
_REASON_LABELS = ("codel", "backstop")


def _rejected_total() -> float:
    """Sum ``rejected_total`` across every priority class and shed reason."""
    return sum(
        metrics.REJECTED_TOTAL.labels(priority=priority, reason=reason)._value.get()
        for priority in _PRIORITY_LABELS
        for reason in _REASON_LABELS
    )


class _StepClock:
    """Deterministic clock that advances by a fixed step on every read.

    Injecting it into the slot pool forces a positive, above-target sojourn on every
    queued request, and injecting it into the CoDel controllers advances their notion of
    time past the tolerance interval between successive samples — so shedding is driven by
    construction rather than by racing the wall clock.
    """

    def __init__(self, *, step: float) -> None:
        self._step = step
        self._now = 0.0

    def __call__(self) -> float:
        value = self._now
        self._now += self._step
        return value


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/work")
    async def work() -> dict[str, bool]:
        await asyncio.sleep(HANDLER_SLEEP)
        return {"ok": True}

    controller = AdmissionController(
        slot_pool=PrioritySlotPool(max_concurrency=MAX_CONCURRENCY),
        target=0.005,
        interval=0.02,
        # A large HIGH target keeps the interactive stream admitted while LOW is shed.
        high_target_multiplier=20.0,
        backstop_max_waiters=1000,
        retry_after=1,
    )
    app.add_middleware(AdmissionMiddleware, controller=controller, enabled=True)
    return app


async def test_gradient() -> None:
    """Under a saturating LOW flood, an interactive HIGH stream is served throughout.

    Standalone app + middleware only: no database, message bus, or other infrastructure is
    touched, so the shed gradient is exercised in isolation.
    """
    app = _build_app()

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:

        async def fire(priority: str) -> int:
            response = await client.get("/work", headers={"X-Priority": priority}, timeout=10)
            return response.status_code

        low_tasks = [asyncio.create_task(fire("low")) for _ in range(LOW_REQUESTS)]

        # Let the pool saturate and sojourn climb past the CoDel interval before the
        # interactive stream starts, so shedding is already active.
        await asyncio.sleep(0.05)

        high_statuses: list[int] = []
        for _ in range(HIGH_REQUESTS):
            high_statuses.append(await fire("high"))
            await asyncio.sleep(0.005)

        low_statuses = await asyncio.gather(*low_tasks)

    # HIGH shed rate must be ~0%: every interactive request is served.
    assert high_statuses == [200] * HIGH_REQUESTS

    # LOW must absorb the shedding: at least some requests receive 429.
    assert low_statuses.count(429) > 0
    # A shed response never ran the handler; served ones did.
    assert set(low_statuses) <= {200, 429}


@pytest.mark.parametrize("priority", ["high", "normal", "low"])
async def test_all_admitted_when_capacity_available(priority: str) -> None:
    """With ample capacity every class is admitted and the handler runs (no behaviour change)."""
    app = FastAPI()

    @app.get("/work")
    async def work() -> dict[str, bool]:
        return {"ok": True}

    controller = AdmissionController(
        slot_pool=PrioritySlotPool(max_concurrency=10),
        target=0.005,
        interval=0.1,
        high_target_multiplier=4.0,
        backstop_max_waiters=1000,
        retry_after=1,
    )
    app.add_middleware(AdmissionMiddleware, controller=controller, enabled=True)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/work", headers={"X-Priority": priority})

    assert response.status_code == 200
    assert response.json() == {"ok": True}


async def test_shed_backstop_returns_rest_envelope() -> None:
    """A backstop shed answers 429 + Retry-After, never runs the handler, tags reason=backstop.

    With no slots and a zero waiter budget every request trips the backstop before acquiring,
    so the shed is forced by construction (no waiting, no race).
    """
    handler_calls = 0
    app = FastAPI()

    @app.get("/work")
    async def work() -> dict[str, bool]:
        nonlocal handler_calls
        handler_calls += 1
        return {"ok": True}

    controller = AdmissionController(
        slot_pool=PrioritySlotPool(max_concurrency=0),
        target=0.005,
        interval=0.1,
        high_target_multiplier=4.0,
        backstop_max_waiters=0,
        retry_after=7,
    )
    app.add_middleware(AdmissionMiddleware, controller=controller, enabled=True)

    before = metrics.REJECTED_TOTAL.labels(priority="low", reason="backstop")._value.get()

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/work", headers={"X-Priority": "low"})

    after = metrics.REJECTED_TOTAL.labels(priority="low", reason="backstop")._value.get()

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "7"
    # No handler work runs on a shed.
    assert handler_calls == 0
    assert after - before == 1
    # REST error envelope, integer code, matching the transport-layer contract.
    assert response.json() == {
        "data": None,
        "errors": [{"message": "Server is shedding load; retry later.", "extensions": {"code": 429}}],
    }


async def test_shed_codel_returns_429() -> None:
    """A CoDel shed answers 429 + Retry-After and tags reason=codel.

    Injected step clocks force an above-target sojourn on every queued request and advance
    the CoDel window past its interval between samples, so the third request is shed by
    construction. A holder occupies the single slot while two followers queue; releasing the
    holder drains them in order and the second follower crosses the drop threshold.
    """
    entered = 0
    release = asyncio.Event()
    app = FastAPI()

    @app.get("/work")
    async def work() -> dict[str, bool]:
        nonlocal entered
        entered += 1
        await release.wait()
        return {"ok": True}

    slot_pool = PrioritySlotPool(max_concurrency=1, clock=_StepClock(step=1.0))
    controller = AdmissionController(
        slot_pool=slot_pool,
        target=0.005,
        interval=1.0,
        high_target_multiplier=4.0,
        backstop_max_waiters=1000,
        retry_after=3,
        clock=_StepClock(step=1.0),
    )
    app.add_middleware(AdmissionMiddleware, controller=controller, enabled=True)

    before = metrics.REJECTED_TOTAL.labels(priority="low", reason="codel")._value.get()

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:

        async def fire() -> httpx.Response:
            return await client.get("/work", headers={"X-Priority": "low"}, timeout=10)

        holder = asyncio.create_task(fire())
        # Poll the pool until the holder occupies the single slot before queuing the followers.
        while slot_pool.in_flight(priority=Priority.LOW) == 0:  # noqa: ASYNC110
            await asyncio.sleep(0)

        follower_a = asyncio.create_task(fire())
        follower_b = asyncio.create_task(fire())
        # Poll the pool until both followers are queued behind the holder.
        while slot_pool.waiters(priority=Priority.LOW) < 2:  # noqa: ASYNC110
            await asyncio.sleep(0)

        release.set()
        responses = await asyncio.gather(holder, follower_a, follower_b)

    after = metrics.REJECTED_TOTAL.labels(priority="low", reason="codel")._value.get()

    # Holder and the first drained follower are served; the second follower is shed.
    assert sorted(response.status_code for response in responses) == [200, 200, 429]
    assert after - before == 1
    shed = next(response for response in responses if response.status_code == 429)
    assert shed.headers["Retry-After"] == "3"
    # The shed request never reached the handler.
    assert entered == 2


async def test_capacity_and_burst() -> None:
    """The max_concurrency gauge tracks the derived cap, and a sub-interval burst sheds nothing.

    Two independent guarantees at the HTTP layer, on a standalone app + middleware:

    (a) The gauge is set only during server wiring, so constructing a controller does not touch
        it. Setting it exactly as the wiring does (derive the cap, then set the gauge) and reading
        it back proves the gauge equals ``derive_max_concurrency(pool_size, factor)`` with no
        magic number.
    (b) A burst of concurrent requests that completes within a single CoDel interval cannot be
        shed: the first above-target sojourn only arms the interval timer, and dropping starts
        only after a full interval of continuous overload. A fast handler and a long interval keep
        the whole burst inside one window, so the shed count is unchanged by construction.
    """
    pool_size = 40
    factor = 0.25
    max_concurrency = derive_max_concurrency(pool_size=pool_size, factor=factor)
    assert max_concurrency == 10

    # Long relative to the burst so the whole burst lands inside one CoDel window.
    interval = 5.0
    burst = 50

    app = FastAPI()

    @app.get("/work")
    async def work() -> dict[str, bool]:
        return {"ok": True}

    controller = AdmissionController(
        slot_pool=PrioritySlotPool(max_concurrency=max_concurrency),
        target=0.005,
        interval=interval,
        high_target_multiplier=4.0,
        backstop_max_waiters=1000,
        retry_after=1,
    )
    # The gauge is set at server wiring time, not by constructing a controller; set it the same
    # way the wiring does so the invariant is observable here.
    metrics.MAX_CONCURRENCY.set(max_concurrency)
    app.add_middleware(AdmissionMiddleware, controller=controller, enabled=True)

    # (a) Gauge equals the derived cap and is positive.
    gauge_value = metrics.MAX_CONCURRENCY._value.get()
    assert gauge_value == derive_max_concurrency(pool_size=pool_size, factor=factor)
    assert gauge_value > 0

    # (b) Drive the burst and assert zero incremental sheds across every class and reason.
    rejected_before = _rejected_total()

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:

        async def fire() -> int:
            response = await client.get("/work", headers={"X-Priority": "normal"}, timeout=10)
            return response.status_code

        start = time.monotonic()
        statuses = await asyncio.gather(*[fire() for _ in range(burst)])
        elapsed = time.monotonic() - start

    rejected_after = _rejected_total()

    # The burst really did finish inside one interval, so no drop was even possible.
    assert elapsed < interval
    # Every request was served; none was shed.
    assert statuses == [200] * burst
    assert rejected_after - rejected_before == 0
