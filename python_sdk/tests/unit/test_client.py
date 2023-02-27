import pytest
from pytest_httpx import HTTPXMock

from infrahub_client import InfrahubClient, InfrahubNode, RepositoryData
from infrahub_client.exceptions import FilterNotFound, NodeNotFound


async def test_init_client():
    await InfrahubClient.init()

    assert True


async def test_get_repositories(mock_branches_list_query, mock_repositories_query):  # pylint: disable=unused-argument
    client = await InfrahubClient.init(address="http://mock", insert_tracker=True)
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

    httpx_mock.add_response(method="POST", json=response, match_headers={"X-Infrahub-Tracker": "query-repository-get"})

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

    httpx_mock.add_response(method="POST", json=response, match_headers={"X-Infrahub-Tracker": "query-repository-get"})

    repo = await client.get(kind="Repository", name__value="infrahub-demo-core")
    assert isinstance(repo, InfrahubNode)
    assert repo.id == "bfae43e8-5ebb-456c-a946-bf64e930710a"


async def test_method_get_not_found(
    httpx_mock: HTTPXMock, client: InfrahubClient, mock_schema_query_01
):  # pylint: disable=unused-argument
    response: dict = {"data": {"repository": []}}
    httpx_mock.add_response(method="POST", json=response, match_headers={"X-Infrahub-Tracker": "query-repository-get"})

    with pytest.raises(NodeNotFound):
        await client.get(kind="Repository", name__value="infrahub-demo-core")


async def test_method_get_found_many(
    httpx_mock: HTTPXMock, client: InfrahubClient, mock_schema_query_01
):  # pylint: disable=unused-argument
    response: dict = {
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

    httpx_mock.add_response(method="POST", json=response, match_headers={"X-Infrahub-Tracker": "query-repository-get"})

    with pytest.raises(IndexError):
        await client.get(kind="Repository", id="bfae43e8-5ebb-456c-a946-bf64e930710a")


async def test_method_get_invalid_filter(
    httpx_mock: HTTPXMock, client: InfrahubClient, mock_schema_query_01
):  # pylint: disable=unused-argument
    with pytest.raises(FilterNotFound):
        await client.get(kind="Repository", name__name="infrahub-demo-core")


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

    httpx_mock.add_response(
        method="POST", json=response, match_headers={"X-Infrahub-Tracker": "query-repository-filters"}
    )

    repos = await client.filters(
        kind="Repository", ids=["bfae43e8-5ebb-456c-a946-bf64e930710a", "9486cfce-87db-479d-ad73-07d80ba96a0f"]
    )
    assert len(repos) == 2


async def test_method_filters_empty(
    httpx_mock: HTTPXMock, client: InfrahubClient, mock_schema_query_01
):  # pylint: disable=unused-argument
    response: dict = {"data": {"repository": []}}
    httpx_mock.add_response(
        method="POST", json=response, match_headers={"X-Infrahub-Tracker": "query-repository-filters"}
    )

    repos = await client.filters(
        kind="Repository", ids=["bfae43e8-5ebb-456c-a946-bf64e930710a", "9486cfce-87db-479d-ad73-07d80ba96a0f"]
    )
    assert len(repos) == 0
