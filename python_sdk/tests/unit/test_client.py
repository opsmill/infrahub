import json

import pytest
from pytest_httpx import HTTPXMock

from infrahub_client import BranchData, InfrahubClient, InfrahubNode, RepositoryData
from infrahub_client.exceptions import FilterNotFound, NodeNotFound
from infrahub_client.graphql import Query


async def test_init_client():
    await InfrahubClient.init()

    assert True


async def test_get_branches(mock_branches_list_query):  # pylint: disable=unused-argument
    client = await InfrahubClient.init(address="http://mock")
    branches = await client.get_list_branches()

    assert len(branches) == 2
    assert isinstance(branches["main"], BranchData)


async def test_get_repositories(mock_branches_list_query, mock_repositories_query):  # pylint: disable=unused-argument
    client = await InfrahubClient.init(address="http://mock")
    repos = await client.get_list_repositories()

    expected_response = RepositoryData(
        id="9486cfce-87db-479d-ad73-07d80ba96a0f",
        name="infrahub-demo-edge",
        location="git@github.com:dgarros/infrahub-demo-edge.git",
        branches={"cr1234": "bbbbbbbbbbbbbbbbbbbb", "main": "aaaaaaaaaaaaaaaaaaaa"},
    )
    assert len(repos) == 1
    assert repos["infrahub-demo-edge"] == expected_response


async def test_method_all(client, mock_query_repository_all_01):  # pylint: disable=unused-argument
    repos = await client.all(kind="Repository")
    assert len(repos) == 2


async def test_method_get_by_id(
    httpx_mock: HTTPXMock, client: InfrahubClient, mock_schema_query_01
):  # pylint: disable=unused-argument
    response = {
        "data": {
            "repository": [
                {
                    "id": "bfae43e8-5ebb-456c-a946-bf64e930710a",
                    "name": {"value": "infrahub-demo-core"},
                    "location": {"value": "git@github.com:opsmill/infrahub-demo-core.git"},
                    "commit": {"value": "bbbbbbbbbbbbbbbbbbbb"},
                }
            ]
        }
    }

    schema = await client.schema.get(kind="Repository")
    query_data = InfrahubNode(client=client, schema=schema).generate_query_data(
        filters={"ids": ["bfae43e8-5ebb-456c-a946-bf64e930710a"]}
    )
    query = Query(query=query_data)
    request_content = json.dumps({"query": query.render()}).encode()
    httpx_mock.add_response(method="POST", json=response, match_content=request_content)

    repo = await client.get(kind="Repository", id="bfae43e8-5ebb-456c-a946-bf64e930710a")
    assert isinstance(repo, InfrahubNode)
    assert repo.id == "bfae43e8-5ebb-456c-a946-bf64e930710a"


async def test_method_get_by_name(
    httpx_mock: HTTPXMock, client: InfrahubClient, mock_schema_query_01
):  # pylint: disable=unused-argument
    response = {
        "data": {
            "repository": [
                {
                    "id": "bfae43e8-5ebb-456c-a946-bf64e930710a",
                    "name": {"value": "infrahub-demo-core"},
                    "location": {"value": "git@github.com:opsmill/infrahub-demo-core.git"},
                    "commit": {"value": "bbbbbbbbbbbbbbbbbbbb"},
                }
            ]
        }
    }

    schema = await client.schema.get(kind="Repository")
    query_data = InfrahubNode(client=client, schema=schema).generate_query_data(
        filters={"name__value": "infrahub-demo-core"}
    )
    query = Query(query=query_data)
    request_content = json.dumps({"query": query.render()}).encode()
    httpx_mock.add_response(method="POST", json=response, match_content=request_content)

    repo = await client.get(kind="Repository", name__value="infrahub-demo-core")
    assert isinstance(repo, InfrahubNode)
    assert repo.id == "bfae43e8-5ebb-456c-a946-bf64e930710a"


async def test_method_get_not_found(
    httpx_mock: HTTPXMock, client: InfrahubClient, mock_schema_query_01
):  # pylint: disable=unused-argument
    response = {"data": {"repository": []}}

    schema = await client.schema.get(kind="Repository")
    query_data = InfrahubNode(client=client, schema=schema).generate_query_data(
        filters={"name__value": "infrahub-demo-core"}
    )
    query = Query(query=query_data)
    request_content = json.dumps({"query": query.render()}).encode()
    httpx_mock.add_response(method="POST", json=response, match_content=request_content)

    with pytest.raises(NodeNotFound):
        repo = await client.get(kind="Repository", name__value="infrahub-demo-core")


async def test_method_get_found_many(
    httpx_mock: HTTPXMock, client: InfrahubClient, mock_schema_query_01
):  # pylint: disable=unused-argument
    response = {
        "data": {
            "repository": [
                {
                    "id": "bfae43e8-5ebb-456c-a946-bf64e930710a",
                    "name": {"value": "infrahub-demo-core"},
                    "location": {"value": "git@github.com:opsmill/infrahub-demo-core.git"},
                    "commit": {"value": "bbbbbbbbbbbbbbbbbbbb"},
                },
                {
                    "id": "9486cfce-87db-479d-ad73-07d80ba96a0f",
                    "name": {"value": "infrahub-demo-edge"},
                    "location": {"value": "git@github.com:opsmill/infrahub-demo-edge.git"},
                    "commit": {"value": "aaaaaaaaaaaaaaaaaaaa"},
                },
            ]
        }
    }

    schema = await client.schema.get(kind="Repository")
    query_data = InfrahubNode(client=client, schema=schema).generate_query_data(
        filters={"ids": ["bfae43e8-5ebb-456c-a946-bf64e930710a"]}
    )
    query = Query(query=query_data)
    request_content = json.dumps({"query": query.render()}).encode()
    httpx_mock.add_response(method="POST", json=response, match_content=request_content)

    with pytest.raises(IndexError):
        repo = await client.get(kind="Repository", id="bfae43e8-5ebb-456c-a946-bf64e930710a")


async def test_method_get_invalid_filter(
    httpx_mock: HTTPXMock, client: InfrahubClient, mock_schema_query_01
):  # pylint: disable=unused-argument
    with pytest.raises(FilterNotFound):
        repo = await client.get(kind="Repository", name__name="infrahub-demo-core")


async def test_method_filters_many(
    httpx_mock: HTTPXMock, client: InfrahubClient, mock_schema_query_01
):  # pylint: disable=unused-argument
    response = {
        "data": {
            "repository": [
                {
                    "id": "bfae43e8-5ebb-456c-a946-bf64e930710a",
                    "name": {"value": "infrahub-demo-core"},
                    "location": {"value": "git@github.com:opsmill/infrahub-demo-core.git"},
                    "commit": {"value": "bbbbbbbbbbbbbbbbbbbb"},
                },
                {
                    "id": "9486cfce-87db-479d-ad73-07d80ba96a0f",
                    "name": {"value": "infrahub-demo-edge"},
                    "location": {"value": "git@github.com:opsmill/infrahub-demo-edge.git"},
                    "commit": {"value": "aaaaaaaaaaaaaaaaaaaa"},
                },
            ]
        }
    }

    schema = await client.schema.get(kind="Repository")
    query_data = InfrahubNode(client=client, schema=schema).generate_query_data(
        filters={"ids": ["bfae43e8-5ebb-456c-a946-bf64e930710a", "9486cfce-87db-479d-ad73-07d80ba96a0f"]}
    )
    query = Query(query=query_data)
    request_content = json.dumps({"query": query.render()}).encode()
    httpx_mock.add_response(method="POST", json=response, match_content=request_content)

    repos = await client.filters(
        kind="Repository", ids=["bfae43e8-5ebb-456c-a946-bf64e930710a", "9486cfce-87db-479d-ad73-07d80ba96a0f"]
    )
    assert len(repos) == 2


async def test_method_filters_empty(
    httpx_mock: HTTPXMock, client: InfrahubClient, mock_schema_query_01
):  # pylint: disable=unused-argument
    response = {"data": {"repository": []}}

    schema = await client.schema.get(kind="Repository")
    query_data = InfrahubNode(client=client, schema=schema).generate_query_data(
        filters={"ids": ["bfae43e8-5ebb-456c-a946-bf64e930710a", "9486cfce-87db-479d-ad73-07d80ba96a0f"]}
    )
    query = Query(query=query_data)
    request_content = json.dumps({"query": query.render()}).encode()
    httpx_mock.add_response(method="POST", json=response, match_content=request_content)

    repos = await client.filters(
        kind="Repository", ids=["bfae43e8-5ebb-456c-a946-bf64e930710a", "9486cfce-87db-479d-ad73-07d80ba96a0f"]
    )
    assert len(repos) == 0
