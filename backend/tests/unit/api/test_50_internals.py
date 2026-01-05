import pytest
from fastapi.testclient import TestClient

from infrahub import config
from infrahub.api import internal
from infrahub.database import InfrahubDatabase
from tests.helpers.fixtures import get_fixtures_dir


async def test_config_endpoint(
    db: InfrahubDatabase, client: TestClient, client_headers, default_branch, register_core_models_schema: None
) -> None:
    with client:
        response = client.get("/api/config", headers=client_headers)

    assert response.status_code == 200
    assert response.json() is not None

    result: dict = response.json()

    assert sorted(result.keys()) == [
        "analytics",
        "experimental_features",
        "installation_type",
        "logging",
        "main",
        "policy",
        "sso",
    ]


@pytest.mark.parametrize("allow_anonymous_access", [False, True])
async def test_config_endpoint_anonymous_account(
    db: InfrahubDatabase,
    client: TestClient,
    default_branch,
    register_core_models_schema: None,
    allow_anonymous_access: bool,
) -> None:
    config.SETTINGS.main.allow_anonymous_access = allow_anonymous_access

    with client:
        response = client.get("/api/config")

    assert response.status_code == 200


async def test_info_endpoint(
    db: InfrahubDatabase, client: TestClient, client_headers, default_branch, register_core_models_schema: None
) -> None:
    with client:
        response = client.get("/api/info", headers=client_headers)

    assert response.status_code == 200
    assert response.json() is not None

    result = response.json()

    assert sorted(result.keys()) == ["deployment_id", "version"]


@pytest.mark.parametrize("allow_anonymous_access", [False, True])
async def test_info_endpoint_anonymous_account(
    db: InfrahubDatabase, client, default_branch, register_core_models_schema: None, allow_anonymous_access: bool
) -> None:
    config.SETTINGS.main.allow_anonymous_access = allow_anonymous_access

    with client:
        response = client.get("/api/info")

    assert response.status_code == 200 if allow_anonymous_access else 401


@pytest.fixture
def override_search_index_path():
    old_search_index_path = config.SETTINGS.main.docs_index_path
    old_search_docs_loader = internal.search_docs_loader
    config.SETTINGS.main.docs_index_path = get_fixtures_dir() / "docs" / "search-index.json"
    internal.search_docs_loader = internal.SearchDocs()
    yield
    config.SETTINGS.main.docs_index_path = old_search_index_path
    internal.search_docs_loader = old_search_docs_loader


@pytest.fixture
def no_search_index_path():
    old_search_index_path = config.SETTINGS.main.docs_index_path
    old_search_docs_loader = internal.search_docs_loader
    config.SETTINGS.main.docs_index_path = get_fixtures_dir() / "docs" / "no-index.json"
    internal.search_docs_loader = internal.SearchDocs()
    yield
    config.SETTINGS.main.docs_index_path = old_search_index_path
    internal.search_docs_loader = old_search_docs_loader


async def test_search_docs(client, override_search_index_path) -> None:
    response = client.get("/api/search/docs?query=guid")

    assert response.status_code == 200
    assert response.json() is not None
    response_json = response.json()
    assert isinstance(response_json, list)
    assert response_json[0]["title"] == "Guides"


async def test_search_docs_limit(client, override_search_index_path) -> None:
    response = client.get("/api/search/docs?query=a&limit=1")

    assert response.status_code == 200
    assert response.json() is not None
    response_json = response.json()
    assert isinstance(response_json, list)
    assert len(response_json) == 1


async def test_no_search_docs(client, no_search_index_path) -> None:
    response = client.get("/api/search/docs?query=guid")

    assert response.status_code == 404
    assert response.json() is not None
    response_json = response.json()
    assert response_json == {
        "data": None,
        "errors": [{"message": "documentation index not found", "extensions": {"code": 404}}],
    }
