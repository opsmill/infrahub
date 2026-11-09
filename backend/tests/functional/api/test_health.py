from __future__ import annotations

from typing import TYPE_CHECKING

from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from tests.helpers.test_client import InfrahubTestClient


class TestHealthEndpoint(TestInfrahubApp):
    async def test_reports_every_backing_service_without_authentication(self, test_client: InfrahubTestClient) -> None:
        response = await test_client.get("/api/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["dependencies"] == [
            {"name": "database", "status": "up", "error": "none"},
            {"name": "message_bus", "status": "up", "error": "none"},
            {"name": "cache", "status": "up", "error": "none"},
            {"name": "task_manager", "status": "up", "error": "none"},
            {"name": "task_manager_db", "status": "up", "error": "none"},
        ]
