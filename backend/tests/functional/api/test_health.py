from __future__ import annotations

from typing import TYPE_CHECKING

from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from tests.helpers.test_client import InfrahubTestClient


class TestHealthEndpoint(TestInfrahubApp):
    async def test_health_returns_200_when_healthy(
        self,
        test_client: InfrahubTestClient,
    ) -> None:
        response = await test_client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert len(data["checks"]) == 3
        assert "timestamp" in data

        check_names = {check["name"] for check in data["checks"]}
        assert check_names == {"database", "message_bus", "cache"}

        for check in data["checks"]:
            assert check["status"] == "up"
            assert check["error"] is None

    async def test_health_no_auth_required(
        self,
        test_client: InfrahubTestClient,
    ) -> None:
        """Verify the health endpoint works without any authentication headers."""
        response = await test_client.get("/health", headers={})
        assert response.status_code == 200

    async def test_health_response_content_type(
        self,
        test_client: InfrahubTestClient,
    ) -> None:
        response = await test_client.get("/health")
        assert response.headers["content-type"] == "application/json"

    async def test_health_response_structure(
        self,
        test_client: InfrahubTestClient,
    ) -> None:
        response = await test_client.get("/health")
        data = response.json()

        assert "status" in data
        assert "checks" in data
        assert "timestamp" in data
        assert isinstance(data["checks"], list)
        assert isinstance(data["status"], str)
        assert isinstance(data["timestamp"], str)

        for check in data["checks"]:
            assert "name" in check
            assert "status" in check
            assert "error" in check

    async def test_health_no_internal_details_exposed(
        self,
        test_client: InfrahubTestClient,
    ) -> None:
        """Verify no hostnames, ports, or connection strings appear in the response."""
        response = await test_client.get("/health")
        body = response.text

        assert "localhost" not in body
        assert "127.0.0.1" not in body
        assert "neo4j://" not in body
        assert "redis://" not in body
        assert "amqp://" not in body
        assert "nats://" not in body
