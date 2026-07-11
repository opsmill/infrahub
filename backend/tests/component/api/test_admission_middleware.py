from __future__ import annotations

import asyncio
import time

import httpx
import pytest
from fastapi import FastAPI

from infrahub import config
from infrahub.api.admission import metrics
from infrahub.api.admission.capacity import derive_max_concurrency
from infrahub.api.admission.controller import AdmissionController, build_admission_controller
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


def _offered(priority: str) -> float:
    return metrics.OFFERED_TOTAL.labels(priority=priority)._value.get()


def _admitted(priority: str) -> float:
    return metrics.ADMITTED_TOTAL.labels(priority=priority)._value.get()


def _rejected(priority: str, reason: str) -> float:
    return metrics.REJECTED_TOTAL.labels(priority=priority, reason=reason)._value.get()


def _sojourn_count(priority: str) -> float:
    """Observation count for a class, summed from the histogram's raw per-bucket counters."""
    return sum(bucket.get() for bucket in metrics.SOJOURN_SECONDS.labels(priority=priority)._buckets)


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


def _admit_app() -> FastAPI:
    """Ample-capacity app: every request is admitted and its handler runs."""
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
    return app


def _backstop_app() -> FastAPI:
    """Zero-capacity, zero-waiter-budget app: every request trips the backstop before acquiring."""
    app = FastAPI()

    @app.get("/work")
    async def work() -> dict[str, bool]:
        return {"ok": True}

    controller = AdmissionController(
        slot_pool=PrioritySlotPool(max_concurrency=0),
        target=0.005,
        interval=0.1,
        high_target_multiplier=4.0,
        backstop_max_waiters=0,
        retry_after=1,
    )
    app.add_middleware(AdmissionMiddleware, controller=controller, enabled=True)
    return app


async def test_metrics() -> None:
    """Mixed-priority traffic moves all eight metric families and keeps the offered accounting exact.

    Three deterministic sub-scenarios drive the shared global registry: an ample-capacity admit
    stream (including header-less requests), a forced backstop shed, and a forced CoDel shed via
    injected step clocks. Every outcome is forced by construction (capacity and clocks), so no
    scenario races the wall clock. Assertions are before/after deltas because the module-level
    metric singletons persist across tests, making absolute values unreliable.
    """
    offered_before = {p: _offered(p) for p in _PRIORITY_LABELS}
    admitted_before = {p: _admitted(p) for p in _PRIORITY_LABELS}
    codel_before = {p: _rejected(p, "codel") for p in _PRIORITY_LABELS}
    backstop_before = {p: _rejected(p, "backstop") for p in _PRIORITY_LABELS}
    sojourn_before = {p: _sojourn_count(p) for p in _PRIORITY_LABELS}
    missing_before = metrics.MISSING_PRIORITY_TOTAL._value.get()

    # The gauge is set at server wiring, not by building a controller; set it the same way.
    max_concurrency = derive_max_concurrency(pool_size=40, factor=0.25)
    metrics.MAX_CONCURRENCY.set(max_concurrency)

    # Scenario 1 — admitted stream: one explicit request per class plus two header-less
    # (missing-priority) requests, all with capacity to spare so each handler runs.
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_admit_app()), base_url="http://test") as client:
        for priority in _PRIORITY_LABELS:
            assert (await client.get("/work", headers={"X-Priority": priority})).status_code == 200
        # No X-Priority header: classified NORMAL, counted as missing.
        assert (await client.get("/work")).status_code == 200
        assert (await client.get("/work")).status_code == 200

    # Scenario 2 — backstop shed: a single LOW request is shed before it ever acquires a slot.
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_backstop_app()), base_url="http://test") as client:
        assert (await client.get("/work", headers={"X-Priority": "low"})).status_code == 429

    # Scenario 3 — CoDel shed: a holder occupies the one slot while two followers queue; draining
    # them under a step clock sheds the second follower. The two acquire attempts that succeed and
    # the shed one all observe a sojourn; only the never-acquired backstop above is exempt.
    entered = 0
    release = asyncio.Event()
    codel_app = FastAPI()

    @codel_app.get("/work")
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
        retry_after=1,
        clock=_StepClock(step=1.0),
    )
    codel_app.add_middleware(AdmissionMiddleware, controller=controller, enabled=True)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=codel_app), base_url="http://test") as client:

        async def fire() -> httpx.Response:
            return await client.get("/work", headers={"X-Priority": "low"}, timeout=10)

        holder = asyncio.create_task(fire())
        while slot_pool.in_flight(priority=Priority.LOW) == 0:  # noqa: ASYNC110
            await asyncio.sleep(0)
        follower_a = asyncio.create_task(fire())
        follower_b = asyncio.create_task(fire())
        while slot_pool.waiters(priority=Priority.LOW) < 2:  # noqa: ASYNC110
            await asyncio.sleep(0)
        release.set()
        responses = await asyncio.gather(holder, follower_a, follower_b)

    assert sorted(response.status_code for response in responses) == [200, 200, 429]

    offered_delta = {p: _offered(p) - offered_before[p] for p in _PRIORITY_LABELS}
    admitted_delta = {p: _admitted(p) - admitted_before[p] for p in _PRIORITY_LABELS}
    codel_delta = {p: _rejected(p, "codel") - codel_before[p] for p in _PRIORITY_LABELS}
    backstop_delta = {p: _rejected(p, "backstop") - backstop_before[p] for p in _PRIORITY_LABELS}
    sojourn_delta = {p: _sojourn_count(p) - sojourn_before[p] for p in _PRIORITY_LABELS}

    # (1) Known counts: the eight families moved with the expected labels.
    assert metrics.MISSING_PRIORITY_TOTAL._value.get() - missing_before == 2
    assert offered_delta == {"high": 1.0, "normal": 3.0, "low": 5.0}
    assert admitted_delta == {"high": 1.0, "normal": 3.0, "low": 3.0}
    assert codel_delta == {"high": 0.0, "normal": 0.0, "low": 1.0}
    assert backstop_delta == {"high": 0.0, "normal": 0.0, "low": 1.0}

    # (2) Per class: every offered request is admitted or shed exactly once.
    for priority in _PRIORITY_LABELS:
        assert offered_delta[priority] == admitted_delta[priority] + codel_delta[priority] + backstop_delta[priority]

    # (5) A sojourn is observed for every request that attempted an acquire — that is, every
    # offered request except the backstop-shed one, which never reached the pool.
    for priority in _PRIORITY_LABELS:
        assert sojourn_delta[priority] == offered_delta[priority] - backstop_delta[priority]
    # Classes that acquired recorded at least one observation.
    assert all(sojourn_delta[priority] > 0 for priority in _PRIORITY_LABELS)

    # (4) in_flight/waiters are readable gauges; releasing through the controller drains them to
    # zero once every request completes, so a served slot never leaves the gauge inflated.
    for priority in _PRIORITY_LABELS:
        in_flight = metrics.IN_FLIGHT.labels(priority=priority)._value.get()
        waiters = metrics.WAITERS.labels(priority=priority)._value.get()
        assert in_flight == 0.0
        assert waiters == 0.0

    # max_concurrency gauge is exported and equals the derived cap with no magic number.
    assert metrics.MAX_CONCURRENCY._value.get() == derive_max_concurrency(pool_size=40, factor=0.25)
    assert metrics.MAX_CONCURRENCY._value.get() > 0


def _offered_total() -> float:
    """Sum ``offered_total`` across every priority class."""
    return sum(_offered(priority) for priority in _PRIORITY_LABELS)


def _shed_everything_controller() -> AdmissionController:
    """Controller with no slots and no waiter budget: every admitted attempt is shed."""
    return AdmissionController(
        slot_pool=PrioritySlotPool(max_concurrency=0),
        target=0.005,
        interval=0.1,
        high_target_multiplier=4.0,
        backstop_max_waiters=0,
        retry_after=1,
    )


@pytest.mark.parametrize("path", ["/health", "/metrics"])
async def test_excluded_path_bypasses_admission(path: str) -> None:
    """An excluded path passes through even behind a shed-everything controller and moves no metric.

    The liveness and scrape endpoints must never be gated: the handler runs (200) and the
    admission layer is never entered, so neither offered nor missing-priority accounting moves.
    """
    app = FastAPI()

    @app.get("/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/metrics")
    async def scrape() -> dict[str, bool]:
        return {"ok": True}

    app.add_middleware(AdmissionMiddleware, controller=_shed_everything_controller(), enabled=True)

    offered_before = _offered_total()
    missing_before = metrics.MISSING_PRIORITY_TOTAL._value.get()

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(path)

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    # The excluded path never reached the admission layer, so no admission metric moved.
    assert _offered_total() - offered_before == 0
    assert metrics.MISSING_PRIORITY_TOTAL._value.get() - missing_before == 0


async def test_kill_switch_passes_through() -> None:
    """With the layer disabled, a request that would be shed instead runs the handler and moves no metric."""
    app = FastAPI()

    @app.get("/work")
    async def work() -> dict[str, bool]:
        return {"ok": True}

    app.add_middleware(AdmissionMiddleware, controller=_shed_everything_controller(), enabled=False)

    offered_before = _offered_total()
    missing_before = metrics.MISSING_PRIORITY_TOTAL._value.get()

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/work", headers={"X-Priority": "low"})

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    # Disabled short-circuits before the controller, so no admission metric moved.
    assert _offered_total() - offered_before == 0
    assert metrics.MISSING_PRIORITY_TOTAL._value.get() - missing_before == 0


async def test_handler_exception_releases_slot() -> None:
    """A handler that raises still returns its slot, so the single-slot pool admits the next request."""
    app = FastAPI()

    @app.get("/boom")
    async def boom() -> dict[str, bool]:
        raise ValueError("handler exploded")

    @app.get("/work")
    async def work() -> dict[str, bool]:
        return {"ok": True}

    slot_pool = PrioritySlotPool(max_concurrency=1)
    controller = AdmissionController(
        slot_pool=slot_pool,
        target=0.005,
        interval=0.1,
        high_target_multiplier=4.0,
        backstop_max_waiters=1000,
        retry_after=1,
    )
    app.add_middleware(AdmissionMiddleware, controller=controller, enabled=True)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        with pytest.raises(ValueError, match=r"^handler exploded$"):
            await client.get("/boom", headers={"X-Priority": "normal"})

        # The finally released the failed request's slot, so the pool is whole again.
        assert slot_pool.available == 1
        assert slot_pool.in_flight(priority=Priority.NORMAL) == 0

        # A leak would block here forever; instead the next request is admitted and served.
        response = await client.get("/work", headers={"X-Priority": "normal"})

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert metrics.IN_FLIGHT.labels(priority="normal")._value.get() == 0.0
    assert slot_pool.available == 1


async def test_build_admission_controller_sets_gauge() -> None:
    """The real settings-reading factory returns a usable controller and sets the max-concurrency gauge."""
    controller = build_admission_controller()

    assert isinstance(controller, AdmissionController)
    expected = derive_max_concurrency(
        pool_size=config.SETTINGS.database.max_connection_pool_size,
        factor=config.SETTINGS.api.backpressure_max_concurrency_factor,
    )
    assert metrics.MAX_CONCURRENCY._value.get() == expected
