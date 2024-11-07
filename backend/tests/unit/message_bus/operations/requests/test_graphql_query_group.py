import os
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
import ujson
from infrahub_sdk import Config, InfrahubClient
from pytest_httpx import HTTPXMock

from infrahub.database import InfrahubDatabase
from infrahub.groups.models import RequestGraphQLQueryGroupUpdate
from infrahub.groups.tasks import update_graphql_query_group
from tests.helpers.utils import init_service_with_client


@pytest.fixture
async def mock_schema_query_02(helper, httpx_mock: HTTPXMock) -> HTTPXMock:
    response_text = Path(os.path.join(helper.get_fixtures_dir(), "schemas", "schema_02.json")).read_text(
        encoding="UTF-8"
    )

    httpx_mock.add_response(method="GET", url="http://mock/api/schema?branch=main", json=ujson.loads(response_text))
    return httpx_mock


async def test_graphql_group_update(db: InfrahubDatabase, httpx_mock: HTTPXMock, mock_schema_query_02):
    q1 = str(uuid.uuid4())
    p1 = str(uuid.uuid4())
    p2 = str(uuid.uuid4())
    c1 = str(uuid.uuid4())
    c2 = str(uuid.uuid4())
    c3 = str(uuid.uuid4())
    r1 = str(uuid.uuid4())

    model = RequestGraphQLQueryGroupUpdate(
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

    with init_service_with_client(client=client), patch("infrahub.groups.tasks.add_branch_tag"):
        # add_branch_tag requires a prefect client, ie it does not work with WorkflowLocal
        response1 = {
            "data": {
                "CoreGraphQLQueryGroupUpsert": {"ok": True, "object": {"id": "957aea37-4510-4386-916f-3febd6665ae6"}}
            }
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

        await update_graphql_query_group.fn(model=model)
