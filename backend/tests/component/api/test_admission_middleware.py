from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi import FastAPI

from infrahub.api.admission.controller import AdmissionController
from infrahub.api.admission.middleware import AdmissionMiddleware
from infrahub.api.admission.slot_pool import PrioritySlotPool

HANDLER_SLEEP = 0.02
MAX_CONCURRENCY = 2
LOW_REQUESTS = 60
HIGH_REQUESTS = 15


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
