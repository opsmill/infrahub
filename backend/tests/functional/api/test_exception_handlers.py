from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator
    from tests.helpers.test_client import InfrahubTestClient


class TestExceptionHandlers(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
        prefect_test_fixture: None,
    ) -> None:
        return None

    async def test_unauthenticated_graphql_returns_catalogue_envelope(
        self,
        initial_dataset: None,
        test_client: InfrahubTestClient,
    ) -> None:
        response = await test_client.post(
            "/graphql",
            json={"query": "{ TestingTag { count } }"},
            headers={"Authorization": "Bearer not-a-real-token"},
        )

        assert response.status_code == 401
        body = response.json()
        assert body["data"] is None
        assert len(body["errors"]) == 1
        extensions = body["errors"][0]["extensions"]
        assert extensions["code"] == "AUTHENTICATION_REQUIRED"
        assert extensions["http_status"] == 401
        assert extensions["data"] == {}

    async def test_unauthenticated_rest_response_preserves_integer_code(
        self,
        initial_dataset: None,
        test_client: InfrahubTestClient,
    ) -> None:
        response = await test_client.get("/api/schema", headers={"Authorization": "Bearer not-a-real-token"})

        assert response.status_code == 401
        body = response.json()
        assert body["data"] is None
        assert body["errors"]
        code = body["errors"][0]["extensions"]["code"]
        assert isinstance(code, int)
        assert code == 401
