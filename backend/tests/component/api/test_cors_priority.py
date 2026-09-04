from __future__ import annotations

import httpx
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from infrahub.api.admission.codel import CoDelController
from infrahub.api.admission.controller import AdmissionController
from infrahub.api.admission.middleware import AdmissionMiddleware
from infrahub.api.admission.observers import AdmissionMetricsObserver, SlotPoolMetricsObserver
from infrahub.api.admission.priority import Priority
from infrahub.api.admission.retry_policy import RetryAfterPolicy
from infrahub.api.admission.slot_pool import PrioritySlotPool
from infrahub.config import (
    default_cors_allow_headers,
    default_cors_allow_methods,
    default_cors_expose_headers,
)

_ORIGIN = "https://frontend.example"


class _FakeLoadSignal:
    """Unstressed stand-in; the unconditional backstop sheds before the gate is consulted."""

    def stress_ratio_median(self) -> float:
        return 1.0

    def sample_count(self) -> int:
        return 0


def _shed_everything_controller() -> AdmissionController:
    """Controller with no slots and no waiter budget: every admitted attempt is shed."""
    return AdmissionController(
        slot_pool=PrioritySlotPool(max_concurrency=0, observers=[SlotPoolMetricsObserver()]),
        codel_priority_map={
            Priority.HIGH: CoDelController(target=0.005 * 4.0, interval=0.1),
            Priority.MEDIUM: CoDelController(target=0.005, interval=0.1),
            Priority.LOW: CoDelController(target=0.005, interval=0.1),
        },
        backstop_max_waiters=dict.fromkeys(Priority, 0),
        stress_signal=_FakeLoadSignal(),
        stress_thresholds=dict.fromkeys(Priority, 1.0),
        stress_min_samples=0,
        retry_policy=RetryAfterPolicy(observers=[]),
        observers=[AdmissionMetricsObserver()],
    )


def _build_app(*, cors_outermost: bool = True) -> FastAPI:
    """App wired like the server: CORS from the shipped defaults, wrapping the admission gate.

    A shed-everything controller means every non-exempt request is answered with a 429.
    ``cors_outermost=False`` puts the gate outside CORS instead, which is what proves the
    preflight exemption holds on its own rather than because CORS answered first.
    """
    app = FastAPI()

    @app.post("/work")
    async def work() -> dict[str, bool]:
        return {"ok": True}

    def add_cors() -> None:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[_ORIGIN],
            allow_methods=default_cors_allow_methods(),
            allow_headers=default_cors_allow_headers(),
            allow_credentials=True,
            expose_headers=default_cors_expose_headers(),
        )

    # Publish the controller/kill-switch on app.state as the startup lifespan does, then register
    # the middlewares in the production order (last registered is outermost).
    app.state.admission_controller = _shed_everything_controller()
    app.state.admission_enabled = True

    if not cors_outermost:
        add_cors()
        app.add_middleware(AdmissionMiddleware)
        return app

    app.add_middleware(AdmissionMiddleware)
    add_cors()
    return app


async def test_cors_preflight_allows_x_priority() -> None:
    """A cross-origin preflight succeeds and x-priority is in the allow-headers, even under shedding.

    The gate is placed outside CORS here so the 200 can only mean the preflight bypassed the
    (shed-everything) admission gate; the allow-headers value proves the shipped default lets a
    cross-origin browser send X-Priority.
    """
    app = _build_app(cors_outermost=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.options(
            "/work",
            headers={
                "Origin": _ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "x-priority",
            },
        )

    assert response.status_code == 200
    assert "x-priority" in response.headers["access-control-allow-headers"].lower()


async def test_non_preflight_request_is_still_shed() -> None:
    """The preflight exemption is narrow: a real cross-origin request is still admission-gated."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_build_app()), base_url="http://test") as client:
        response = await client.post("/work", headers={"Origin": _ORIGIN, "X-Priority": "low"})

    assert response.status_code == 429


async def test_shed_response_is_readable_cross_origin() -> None:
    """A shed 429 carries the CORS headers a browser needs to hand the response to the client.

    Without the allow-origin the browser blocks the response outright and the client sees an
    opaque network error; without retry-after in the expose-list it can read the status but not
    the wait the server advised, and falls back to guessing one.
    """
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_build_app()), base_url="http://test") as client:
        response = await client.post("/work", headers={"Origin": _ORIGIN, "X-Priority": "low"})

    assert response.status_code == 429
    assert response.headers["retry-after"]
    assert response.headers["access-control-allow-origin"] == _ORIGIN
    assert "retry-after" in response.headers["access-control-expose-headers"].lower()
