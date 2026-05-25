from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.node import Node
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator
    from tests.helpers.test_client import InfrahubTestClient


def _admin_headers(api_admin_token: str) -> dict[str, str]:
    return {"X-INFRAHUB-KEY": api_admin_token}


async def _post_graphql(
    client: InfrahubTestClient,
    query: str,
    headers: dict[str, str],
    variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"query": query}
    if variables is not None:
        payload["variables"] = variables
    response = await client.post("/graphql", json=payload, headers=headers)
    assert response.status_code == 200
    return response.json()


class TestErrorCatalogue(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
        prefect_test_fixture: None,
    ) -> str:
        await load_schema(db, schema=CAR_SCHEMA, update_db=True)
        person = await Node.init(db=db, schema="TestingPerson")
        await person.new(db=db, name="seed-person", height=180)
        await person.save(db=db)
        return person.id

    async def test_node_not_found_emits_catalogue_envelope(
        self,
        initial_dataset: str,
        test_client: InfrahubTestClient,
        api_admin_token: str,
    ) -> None:
        unknown_id = "17a90b4e-0000-0000-0000-deadbeef0000"
        query = """
        mutation {
            TestingPersonUpdate(
                data: { id: "17a90b4e-0000-0000-0000-deadbeef0000", description: { value: "rename" } }
            ) { ok }
        }
        """
        body = await _post_graphql(client=test_client, query=query, headers=_admin_headers(api_admin_token))
        assert body["data"] == {"TestingPersonUpdate": None}
        assert len(body["errors"]) == 1
        error = body["errors"][0]
        assert error["extensions"]["code"] == "NODE_NOT_FOUND"
        assert error["extensions"]["http_status"] == 404
        assert error["extensions"]["data"] == {"node_kind": "TestingPerson", "identifier": unknown_id}

    async def test_attribute_required_for_single_missing_field(
        self,
        initial_dataset: str,
        test_client: InfrahubTestClient,
        api_admin_token: str,
    ) -> None:
        query = """
        mutation {
            TestingPersonCreate(data: { height: { value: 175 } }) { ok }
        }
        """
        body = await _post_graphql(client=test_client, query=query, headers=_admin_headers(api_admin_token))
        assert len(body["errors"]) == 1
        error = body["errors"][0]
        assert error["extensions"]["code"] == "ATTRIBUTE_REQUIRED"
        assert error["extensions"]["http_status"] == 422
        assert error["extensions"]["data"] == {"node_kind": "TestingPerson", "field_name": "name"}

    async def test_multi_field_validation_returns_one_entry_per_failing_field(
        self,
        initial_dataset: str,
        test_client: InfrahubTestClient,
        api_admin_token: str,
    ) -> None:
        # TestingCar requires name + color attributes AND owner + manufacturer relationships.
        # Submitting an empty payload triggers the resolver's per-field validation fan-out and
        # must produce one errors[] entry per missing field, each carrying its own catalogue
        # code, typed data, and path.
        query = """
        mutation {
            TestingCarCreate(data: {}) { ok }
        }
        """
        body = await _post_graphql(client=test_client, query=query, headers=_admin_headers(api_admin_token))

        assert body["data"] == {"TestingCarCreate": None}
        errors = body["errors"]
        assert len(errors) >= 2, f"expected per-field fan-out, got {len(errors)} entry/entries"

        codes = {error["extensions"]["code"] for error in errors}
        assert codes == {"ATTRIBUTE_REQUIRED"}, codes

        field_names = {error["extensions"]["data"]["field_name"] for error in errors}
        # name and color are mandatory attributes on TestingCar; both must be reported.
        assert {"name", "color"}.issubset(field_names), field_names

        for error in errors:
            assert error["extensions"]["http_status"] == 422
            data = error["extensions"]["data"]
            assert data["node_kind"] == "TestingCar"
            assert error["path"][-1] == data["field_name"], error["path"]

    async def test_undefined_error_falls_back_for_uncatalogued_exception(
        self,
        initial_dataset: str,
        test_client: InfrahubTestClient,
        api_admin_token: str,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # A graphql-core validation error (unknown field) has no original_error — the formatter
        # should still emit UNDEFINED_ERROR with a 500 fallback.
        query = "query { ThisFieldDoesNotExist { id } }"
        caplog.set_level("INFO", logger="infrahub.graphql.errors")
        body = await _post_graphql(client=test_client, query=query, headers=_admin_headers(api_admin_token))
        assert body["errors"], "expected at least one error"
        error = body["errors"][0]
        assert error["extensions"]["code"] == "UNDEFINED_ERROR"
        assert error["extensions"]["http_status"] == 500
        assert error["extensions"]["data"] == {}
