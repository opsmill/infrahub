from __future__ import annotations

import httpx
from fastapi import FastAPI

from infrahub.api import health
from infrahub.health import DependencyCheck, DependencyName, HealthChecker


async def _passes() -> None: ...


async def _refuses_connections() -> None:
    raise ConnectionRefusedError("Connect call failed ('10.0.0.1', 5672)")


async def _get_health(checks: list[DependencyCheck]) -> httpx.Response:
    app = FastAPI()
    app.include_router(health.router, prefix="/api")
    app.state.health_checker = HealthChecker(checks=checks, check_timeout=1, max_report_age=0)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        return await client.get("/api/health")


async def test_healthy_report_is_served_with_200_and_is_never_cached() -> None:
    response = await _get_health([DependencyCheck(name=DependencyName.DATABASE, check=_passes)])

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["status"] == "healthy"
    assert body["dependencies"] == [{"name": "database", "status": "up", "error": "none"}]


async def test_unhealthy_report_is_served_with_503() -> None:
    response = await _get_health(
        [
            DependencyCheck(name=DependencyName.DATABASE, check=_passes),
            DependencyCheck(name=DependencyName.MESSAGE_BUS, check=_refuses_connections),
        ]
    )

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unhealthy"
    assert body["dependencies"] == [
        {"name": "database", "status": "up", "error": "none"},
        {"name": "message_bus", "status": "down", "error": "connection_refused"},
    ]
