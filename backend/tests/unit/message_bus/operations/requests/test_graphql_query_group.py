import os
import uuid
from pathlib import Path

import pytest
import ujson
from infrahub_sdk import Config, InfrahubClient
from pytest_httpx import HTTPXMock

from infrahub.database import InfrahubDatabase
from infrahub.message_bus import messages
from infrahub.message_bus.operations.requests.graphql_query_group import update
from infrahub.services import InfrahubServices


@pytest.fixture
async def mock_schema_query_02(helper, httpx_mock: HTTPXMock) -> HTTPXMock:
    response_text = Path(os.path.join(helper.get_fixtures_dir(), "schemas", "schema_02.json")).read_text(
        encoding="UTF-8"
    )

    httpx_mock.add_response(method="GET", url="http://mock/api/schema/?branch=main", json=ujson.loads(response_text))
    return httpx_mock


async def test_graphql_group_update(db: InfrahubDatabase, httpx_mock: HTTPXMock, mock_schema_query_02):
    q1 = str(uuid.uuid4())
    p1 = str(uuid.uuid4())
    p2 = str(uuid.uuid4())
    c1 = str(uuid.uuid4())
    c2 = str(uuid.uuid4())
    c3 = str(uuid.uuid4())
    r1 = str(uuid.uuid4())

    message = messages.RequestGraphQLQueryGroupUpdate(
        query_id=q1,
        query_name="query01",
        branch="main",
        related_node_ids={p1, p2, c1, c2, c3},
        subscribers={r1},
        params={"name": "John"},
    )
    config = Config(address="http://mock", insert_tracker=True)
    client = InfrahubClient(
        config=config,
    )
    service = InfrahubServices(client=client)

    response1 = {
        "data": {"CoreGraphQLQueryGroupUpsert": {"ok": True, "object": {"id": "957aea37-4510-4386-916f-3febd6665ae6"}}}
    }

    httpx_mock.add_response(
        method="POST",
        json=response1,
        match_headers={"X-Infrahub-Tracker": "mutation-coregraphqlquerygroup-upsert"},
    )

    response2 = {"data": {"RelationshipAdd": {"ok": True}}}
    httpx_mock.add_response(
        method="POST",
        json=response2,
        match_headers={"X-Infrahub-Tracker": "mutation-relationshipadd"},
    )

    await update(message=message, service=service)
