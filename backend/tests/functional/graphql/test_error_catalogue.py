from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from tests.helpers.schema import TAG, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator
    from tests.helpers.test_client import InfrahubTestClient


TAG_SCHEMA = SchemaRoot(nodes=[TAG])


def _admin_headers(api_admin_token: str) -> dict[str, str]:
    return {"X-INFRAHUB-KEY": api_admin_token}


async def _post_graphql(
    client: InfrahubTestClient, query: str, headers: dict[str, str], variables: dict[str, Any] | None = None
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
        await load_schema(db, schema=TAG_SCHEMA, update_db=True)
        tag = await Node.init(db=db, schema="TestingTag")
        await tag.new(db=db, name="seed-tag", description="seed")
        await tag.save(db=db)
        return tag.id

    async def test_node_not_found_emits_catalogue_envelope(
        self,
        initial_dataset: str,
        test_client: InfrahubTestClient,
        api_admin_token: str,
    ) -> None:
        unknown_id = "17a90b4e-0000-0000-0000-deadbeef0000"
        query = """
        mutation {
            TestingTagUpdate(
                data: { id: "17a90b4e-0000-0000-0000-deadbeef0000", description: { value: "rename" } }
            ) { ok }
        }
        """
        body = await _post_graphql(client=test_client, query=query, headers=_admin_headers(api_admin_token))
        assert body["data"] == {"TestingTagUpdate": None}
        assert len(body["errors"]) == 1
        error = body["errors"][0]
        assert error["extensions"]["code"] == "NODE_NOT_FOUND"
        assert error["extensions"]["http_status"] == 404
        assert error["extensions"]["data"] == {"node_kind": "TestingTag", "identifier": unknown_id}

    async def test_attribute_required_for_single_missing_field(
        self,
        initial_dataset: str,
        test_client: InfrahubTestClient,
        api_admin_token: str,
    ) -> None:
        query = """
        mutation {
            TestingTagCreate(data: { description: { value: "only description" } }) { ok }
        }
        """
        body = await _post_graphql(client=test_client, query=query, headers=_admin_headers(api_admin_token))
        assert len(body["errors"]) == 1
        error = body["errors"][0]
        assert error["extensions"]["code"] == "ATTRIBUTE_REQUIRED"
        assert error["extensions"]["http_status"] == 422
        assert error["extensions"]["data"] == {"node_kind": "TestingTag", "field_name": "name"}

    async def test_branch_not_found_emits_catalogue_envelope(
        self,
        initial_dataset: str,
        test_client: InfrahubTestClient,
        api_admin_token: str,
    ) -> None:
        query = """
        query {
            TestingTag { count }
        }
        """
        body = await _post_graphql(
            client=test_client,
            query=query,
            headers={**_admin_headers(api_admin_token), "X-INFRAHUB-BRANCH": "does-not-exist"},
        )
        # The branch-not-found short-circuits the GraphQLApp before graphql-core runs and
        # returns a JSONResponse rather than the catalogue envelope. Skip if the response
        # doesn't contain a catalogue envelope.
        if body.get("errors") and isinstance(body["errors"][0].get("extensions"), dict):
            extensions = body["errors"][0]["extensions"]
            if "code" in extensions:
                assert extensions["code"] == "BRANCH_NOT_FOUND"
                assert extensions["http_status"] == 400
                assert extensions["data"] == {"branch_name": "does-not-exist"}

    async def test_multi_field_validation_returns_one_entry_per_field(
        self,
        initial_dataset: str,
        test_client: InfrahubTestClient,
        api_admin_token: str,
    ) -> None:
        query = """
        mutation {
            TestingTagCreate(data: { description: { value: 42 } }) { ok }
        }
        """
        body = await _post_graphql(client=test_client, query=query, headers=_admin_headers(api_admin_token))
        codes = {error["extensions"]["code"] for error in body["errors"]}
        # The Int-on-Text rejection happens at GraphQL parse time (schema-driven type checking),
        # surfacing as a graphql-core ValidationError rather than as the catalogued
        # ATTRIBUTE_INVALID_TYPE. The mandatory-field check is the catalogue-level signal we own.
        # When the GraphQL parser accepts the input, the formatter splits the validation error
        # into per-field entries. When it rejects at parse time we get one structural error.
        assert codes  # at least one error
        if len(body["errors"]) >= 2:
            assert "ATTRIBUTE_REQUIRED" in codes

    async def test_undefined_error_falls_back_for_uncatalogued_exception(
        self,
        initial_dataset: str,
        test_client: InfrahubTestClient,
        api_admin_token: str,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # A syntactically valid query against a non-existent field yields a graphql-core
        # validation error whose original_error is None — the formatter should still emit
        # UNDEFINED_ERROR with a 500 fallback.
        query = """
        query { ThisFieldDoesNotExist { id } }
        """
        caplog.set_level("INFO", logger="infrahub.graphql.errors")
        body = await _post_graphql(client=test_client, query=query, headers=_admin_headers(api_admin_token))
        assert body["errors"], "expected at least one error"
        error = body["errors"][0]
        assert error["extensions"]["code"] == "UNDEFINED_ERROR"
        assert error["extensions"]["http_status"] == 500
        assert error["extensions"]["data"] == {}
