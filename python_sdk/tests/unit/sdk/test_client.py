import inspect

import pytest
from pytest_httpx import HTTPXMock

from infrahub_sdk import InfrahubClient, InfrahubClientSync
from infrahub_sdk.exceptions import FilterNotFoundError, NodeNotFoundError
from infrahub_sdk.node import InfrahubNode, InfrahubNodeSync

async_client_methods = [method for method in dir(InfrahubClient) if not method.startswith("_")]
sync_client_methods = [method for method in dir(InfrahubClientSync) if not method.startswith("_")]

client_types = ["standard", "sync"]


async def test_method_sanity():
    """Validate that there is at least one public method and that both clients look the same."""
    assert async_client_methods
    assert async_client_methods == sync_client_methods


@pytest.mark.parametrize("method", async_client_methods)
async def test_validate_method_signature(
    method,
    replace_async_return_annotation,
    replace_sync_return_annotation,
    replace_async_parameter_annotations,
    replace_sync_parameter_annotations,
):
    async_method = getattr(InfrahubClient, method)
    sync_method = getattr(InfrahubClientSync, method)
    async_sig = inspect.signature(async_method)
    sync_sig = inspect.signature(sync_method)

    assert replace_async_parameter_annotations(async_sig.parameters) == replace_async_parameter_annotations(
        sync_sig.parameters
    )
    assert replace_sync_parameter_annotations(async_sig.parameters) == replace_sync_parameter_annotations(
        sync_sig.parameters
    )
    assert async_sig.return_annotation == replace_sync_return_annotation(sync_sig.return_annotation)
    assert replace_async_return_annotation(async_sig.return_annotation) == sync_sig.return_annotation


async def test_init_client():
    await InfrahubClient.init()

    assert True


async def test_init_client_sync():
    InfrahubClientSync.init()

    assert True


async def test_init_with_invalid_address():
    with pytest.raises(ValueError) as exc:
        await InfrahubClient.init(address="missing-schema")

    assert "The configured address is not a valid url" in str(exc.value)


async def test_get_repositories(client, mock_branches_list_query, mock_schema_query_02, mock_repositories_query):  # pylint: disable=unused-argument
    repos = await client.get_list_repositories()

    assert len(repos) == 2
    assert repos["infrahub-demo-edge"].repository.get_kind() == "CoreRepository"
    assert repos["infrahub-demo-edge"].repository.id == "9486cfce-87db-479d-ad73-07d80ba96a0f"
    assert repos["infrahub-demo-edge"].branches == {"cr1234": "bbbbbbbbbbbbbbbbbbbb", "main": "aaaaaaaaaaaaaaaaaaaa"}
    assert repos["infrahub-demo-edge-read-only"].repository.get_kind() == "CoreReadOnlyRepository"
    assert repos["infrahub-demo-edge-read-only"].repository.id == "aeff0feb-6a49-406e-b395-de7b7856026d"
    assert repos["infrahub-demo-edge-read-only"].branches == {
        "cr1234": "dddddddddddddddddddd",
        "main": "cccccccccccccccccccc",
    }


@pytest.mark.parametrize("client_type", client_types)
async def test_method_all_with_limit(clients, mock_query_repository_page1_2, client_type):  # pylint: disable=unused-argument
    if client_type == "standard":
        repos = await clients.standard.all(kind="CoreRepository", limit=3)
        assert not clients.standard.store._store["CoreRepository"]

        repos = await clients.standard.all(kind="CoreRepository", populate_store=True, limit=3)
        assert len(clients.standard.store._store["CoreRepository"]) == 3
    else:
        repos = clients.sync.all(kind="CoreRepository", limit=3)
        assert not clients.sync.store._store["CoreRepository"]

        repos = clients.sync.all(kind="CoreRepository", populate_store=True, limit=3)
        assert len(clients.sync.store._store["CoreRepository"]) == 3

    assert len(repos) == 3


@pytest.mark.parametrize("client_type", client_types)
async def test_method_all_multiple_pages(
    clients, mock_query_repository_page1_2, mock_query_repository_page2_2, client_type
):  # pylint: disable=unused-argument
    if client_type == "standard":
        repos = await clients.standard.all(kind="CoreRepository")
        assert not clients.standard.store._store["CoreRepository"]

        repos = await clients.standard.all(kind="CoreRepository", populate_store=True)
        assert len(clients.standard.store._store["CoreRepository"]) == 5
    else:
        repos = clients.sync.all(kind="CoreRepository")
        assert not clients.sync.store._store["CoreRepository"]

        repos = clients.sync.all(kind="CoreRepository", populate_store=True)
        assert len(clients.sync.store._store["CoreRepository"]) == 5

    assert len(repos) == 5


@pytest.mark.parametrize("client_type", client_types)
async def test_method_all_single_page(clients, mock_query_repository_page1_1, client_type):  # pylint: disable=unused-argument
    if client_type == "standard":
        repos = await clients.standard.all(kind="CoreRepository")
        assert not clients.standard.store._store["CoreRepository"]

        repos = await clients.standard.all(kind="CoreRepository", populate_store=True)
        assert len(clients.standard.store._store["CoreRepository"]) == 2
    else:
        repos = clients.sync.all(kind="CoreRepository")
        assert not clients.sync.store._store["CoreRepository"]

        repos = clients.sync.all(kind="CoreRepository", populate_store=True)
        assert len(clients.sync.store._store["CoreRepository"]) == 2

    assert len(repos) == 2


@pytest.mark.parametrize("client_type", client_types)
async def test_method_all_generic(clients, mock_query_corenode_page1_1, client_type):  # pylint: disable=unused-argument
    if client_type == "standard":
        nodes = await clients.standard.all(kind="CoreNode")
    else:
        nodes = clients.sync.all(kind="CoreNode")

    assert len(nodes) == 2
    assert nodes[0].typename == "BuiltinTag"
    assert nodes[1].typename == "BuiltinLocation"


@pytest.mark.parametrize("client_type", client_types)
async def test_method_get_by_id(httpx_mock: HTTPXMock, clients, mock_schema_query_01, client_type):  # pylint: disable=unused-argument
    response = {
        "data": {
            "CoreRepository": {
                "edges": [
                    {
                        "node": {
                            "__typename": "CoreRepository",
                            "id": "bfae43e8-5ebb-456c-a946-bf64e930710a",
                            "name": {"value": "infrahub-demo-core"},
                            "location": {"value": "git@github.com:opsmill/infrahub-demo-core.git"},
                            "commit": {"value": "bbbbbbbbbbbbbbbbbbbb"},
                        }
                    }
                ]
            }
        }
    }

    response_id = "bfae43e8-5ebb-456c-a946-bf64e930710a"
    httpx_mock.add_response(
        method="POST",
        json=response,
        match_headers={"X-Infrahub-Tracker": "query-corerepository-page1"},
    )

    if client_type == "standard":
        repo = await clients.standard.get(kind="CoreRepository", id=response_id)
        assert isinstance(repo, InfrahubNode)
        with pytest.raises(NodeNotFoundError):
            assert clients.standard.store.get(key=response_id)

        repo = await clients.standard.get(kind="CoreRepository", id=response_id, populate_store=True)
        assert clients.standard.store.get(key=response_id)
    else:
        repo = clients.sync.get(kind="CoreRepository", id=response_id)
        assert isinstance(repo, InfrahubNodeSync)
        with pytest.raises(NodeNotFoundError):
            assert clients.sync.store.get(key=response_id)

        repo = clients.sync.get(kind="CoreRepository", id=response_id, populate_store=True)
        assert clients.sync.store.get(key=response_id)


@pytest.mark.parametrize("client_type", client_types)
async def test_method_get_by_default_filter(httpx_mock: HTTPXMock, clients, mock_schema_query_01, client_type):  # pylint: disable=unused-argument
    response = {
        "data": {
            "CoreRepository": {
                "edges": [
                    {
                        "node": {
                            "__typename": "CoreRepository",
                            "id": "bfae43e8-5ebb-456c-a946-bf64e930710a",
                            "name": {"value": "infrahub-demo-core"},
                            "location": {"value": "git@github.com:opsmill/infrahub-demo-core.git"},
                            "commit": {"value": "bbbbbbbbbbbbbbbbbbbb"},
                        }
                    }
                ]
            }
        }
    }

    response_id = "bfae43e8-5ebb-456c-a946-bf64e930710a"
    httpx_mock.add_response(
        method="POST",
        json=response,
        match_headers={"X-Infrahub-Tracker": "query-corerepository-page1"},
    )

    if client_type == "standard":
        repo = await clients.standard.get(kind="CoreRepository", id="infrahub-demo-core")
        assert isinstance(repo, InfrahubNode)
        with pytest.raises(NodeNotFoundError):
            assert clients.standard.store.get(key=response_id)

        repo = await clients.standard.get(kind="CoreRepository", id="infrahub-demo-core", populate_store=True)
        assert clients.standard.store.get(key=response_id)
    else:
        repo = clients.sync.get(kind="CoreRepository", id="infrahub-demo-core")
        assert isinstance(repo, InfrahubNodeSync)
        with pytest.raises(NodeNotFoundError):
            assert clients.sync.store.get(key="infrahub-demo-core")

        repo = clients.sync.get(kind="CoreRepository", id="infrahub-demo-core", populate_store=True)
        assert clients.sync.store.get(key=response_id)


@pytest.mark.parametrize("client_type", client_types)
async def test_method_get_by_name(httpx_mock: HTTPXMock, clients, mock_schema_query_01, client_type):  # pylint: disable=unused-argument
    response = {
        "data": {
            "CoreRepository": {
                "edges": [
                    {
                        "node": {
                            "__typename": "CoreRepository",
                            "id": "bfae43e8-5ebb-456c-a946-bf64e930710a",
                            "name": {"value": "infrahub-demo-core"},
                            "location": {"value": "git@github.com:opsmill/infrahub-demo-core.git"},
                            "commit": {"value": "bbbbbbbbbbbbbbbbbbbb"},
                        }
                    }
                ]
            }
        }
    }

    httpx_mock.add_response(
        method="POST",
        json=response,
        match_headers={"X-Infrahub-Tracker": "query-corerepository-page1"},
    )

    if client_type == "standard":
        repo = await clients.standard.get(kind="CoreRepository", name__value="infrahub-demo-core")
        assert isinstance(repo, InfrahubNode)
    else:
        repo = clients.sync.get(kind="CoreRepository", name__value="infrahub-demo-core")
        assert isinstance(repo, InfrahubNodeSync)
    assert repo.id == "bfae43e8-5ebb-456c-a946-bf64e930710a"


@pytest.mark.parametrize("client_type", client_types)
async def test_method_get_not_found(httpx_mock: HTTPXMock, clients, mock_query_repository_page1_empty, client_type):  # pylint: disable=unused-argument
    with pytest.raises(NodeNotFoundError):
        if client_type == "standard":
            await clients.standard.get(kind="CoreRepository", name__value="infrahub-demo-core")
        else:
            clients.sync.get(kind="CoreRepository", name__value="infrahub-demo-core")


@pytest.mark.parametrize("client_type", client_types)
async def test_method_get_found_many(
    httpx_mock: HTTPXMock,
    clients,
    mock_schema_query_01,
    mock_query_repository_page1_1,
    client_type,
):  # pylint: disable=unused-argument
    with pytest.raises(IndexError):
        if client_type == "standard":
            await clients.standard.get(kind="CoreRepository", id="bfae43e8-5ebb-456c-a946-bf64e930710a")
        else:
            clients.sync.get(kind="CoreRepository", id="bfae43e8-5ebb-456c-a946-bf64e930710a")


@pytest.mark.parametrize("client_type", client_types)
async def test_method_get_invalid_filter(httpx_mock: HTTPXMock, clients, mock_schema_query_01, client_type):  # pylint: disable=unused-argument
    with pytest.raises(FilterNotFoundError) as excinfo:
        if client_type == "standard":
            await clients.standard.get(kind="CoreRepository", name__name="infrahub-demo-core")
        else:
            clients.sync.get(kind="CoreRepository", name__name="infrahub-demo-core")
    assert isinstance(excinfo.value.message, str)
    assert "'name__name' is not a valid filter for 'CoreRepository'" in excinfo.value.message
    assert "default_branch__value" in excinfo.value.message
    assert "default_branch__value" in excinfo.value.filters


@pytest.mark.parametrize("client_type", client_types)
async def test_method_filters_many(httpx_mock: HTTPXMock, clients, mock_query_repository_page1_1, client_type):  # pylint: disable=unused-argument
    if client_type == "standard":
        repos = await clients.standard.filters(
            kind="CoreRepository",
            ids=[
                "bfae43e8-5ebb-456c-a946-bf64e930710a",
                "9486cfce-87db-479d-ad73-07d80ba96a0f",
            ],
        )
        assert len(repos) == 2
        assert not clients.standard.store._store["CoreRepository"]

        repos = await clients.standard.filters(
            kind="CoreRepository",
            ids=[
                "bfae43e8-5ebb-456c-a946-bf64e930710a",
                "9486cfce-87db-479d-ad73-07d80ba96a0f",
            ],
            populate_store=True,
        )
        assert len(clients.standard.store._store["CoreRepository"]) == 2
        assert len(repos) == 2
    else:
        repos = clients.sync.filters(
            kind="CoreRepository",
            ids=[
                "bfae43e8-5ebb-456c-a946-bf64e930710a",
                "9486cfce-87db-479d-ad73-07d80ba96a0f",
            ],
        )
        assert len(repos) == 2
        assert not clients.sync.store._store["CoreRepository"]

        repos = clients.sync.filters(
            kind="CoreRepository",
            ids=[
                "bfae43e8-5ebb-456c-a946-bf64e930710a",
                "9486cfce-87db-479d-ad73-07d80ba96a0f",
            ],
            populate_store=True,
        )
        assert len(clients.sync.store._store["CoreRepository"]) == 2
        assert len(repos) == 2


@pytest.mark.parametrize("client_type", client_types)
async def test_method_filters_empty(httpx_mock: HTTPXMock, clients, mock_query_repository_page1_empty, client_type):  # pylint: disable=unused-argument
    if client_type == "standard":
        repos = await clients.standard.filters(
            kind="CoreRepository",
            ids=[
                "bfae43e8-5ebb-456c-a946-bf64e930710a",
                "9486cfce-87db-479d-ad73-07d80ba96a0f",
            ],
        )
    else:
        repos = clients.sync.filters(
            kind="CoreRepository",
            ids=[
                "bfae43e8-5ebb-456c-a946-bf64e930710a",
                "9486cfce-87db-479d-ad73-07d80ba96a0f",
            ],
        )
    assert len(repos) == 0


EXPECTED_ECHO = """URL: http://mock/graphql
QUERY:

    query GetTags($name: String!) {
    BuiltinTag(name__value: $name) {
        edges {
        node {
            id
            display_label
        }
        }
    }
    }

VARIABLES:
{
    "name": "red"
}

"""


@pytest.mark.parametrize("client_type", client_types)
async def test_query_echo(httpx_mock: HTTPXMock, echo_clients, client_type):  # pylint: disable=unused-argument
    httpx_mock.add_response(
        method="POST",
        json={"data": {"BuiltinTag": {"edges": []}}},
    )

    query = """
    query GetTags($name: String!) {
    BuiltinTag(name__value: $name) {
        edges {
        node {
            id
            display_label
        }
        }
    }
    }
"""

    variables = {"name": "red"}

    if client_type == "standard":
        response = await echo_clients.standard.execute_graphql(query=query, variables=variables)
    else:
        response = echo_clients.sync.execute_graphql(query=query, variables=variables)

    assert response == {"BuiltinTag": {"edges": []}}
    assert echo_clients.stdout.getvalue().splitlines() == EXPECTED_ECHO.splitlines()


@pytest.mark.parametrize("client_type", client_types)
async def test_clone(clients, client_type):
    if client_type == "standard":
        clone = clients.standard.clone()
        assert clone.config == clients.standard.config
        assert isinstance(clone, InfrahubClient)
    else:
        clone = clients.sync.clone()
        assert clone.config == clients.sync.config
        assert isinstance(clone, InfrahubClientSync)
