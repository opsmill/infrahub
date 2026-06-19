from collections.abc import Generator
from typing import Any

import pytest
from fast_depends import Provider
from fastapi.testclient import TestClient

from infrahub import config
from infrahub.api import internal
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.message_bus.messages import RefreshSettingsResponseDelay
from infrahub.message_bus.operations.refresh import settings as refresh_settings
from infrahub.workers.dependencies import build_message_bus
from tests.conftest import TestHelper
from tests.helpers.fixtures import get_fixtures_dir


async def test_config_endpoint(
    db: InfrahubDatabase,
    client: TestClient,
    client_headers: dict[str, str],
    default_branch: Branch,
    register_core_models_schema: None,
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
    default_branch: Branch,
    register_core_models_schema: None,
    allow_anonymous_access: bool,
) -> None:
    config.SETTINGS.main.allow_anonymous_access = allow_anonymous_access

    with client:
        response = client.get("/api/config")

    assert response.status_code == 200


async def test_info_endpoint(
    db: InfrahubDatabase,
    client: TestClient,
    client_headers: dict[str, str],
    default_branch: Branch,
    register_core_models_schema: None,
) -> None:
    with client:
        response = client.get("/api/info", headers=client_headers)

    assert response.status_code == 200
    assert response.json() is not None

    result = response.json()

    assert sorted(result.keys()) == ["deployment_id", "version"]


@pytest.mark.parametrize("allow_anonymous_access", [False, True])
async def test_info_endpoint_anonymous_account(
    db: InfrahubDatabase,
    client: TestClient,
    default_branch: Branch,
    register_core_models_schema: None,
    allow_anonymous_access: bool,
) -> None:
    config.SETTINGS.main.allow_anonymous_access = allow_anonymous_access

    with client:
        response = client.get("/api/info")

    assert response.status_code == 200 if allow_anonymous_access else 401


@pytest.fixture
def override_search_index_path() -> Generator[None, None, None]:
    old_search_index_path = config.SETTINGS.main.docs_index_path
    old_search_docs_loader = internal.search_docs_loader
    config.SETTINGS.main.docs_index_path = get_fixtures_dir() / "docs" / "search-index.json"
    internal.search_docs_loader = internal.SearchDocs()
    yield
    config.SETTINGS.main.docs_index_path = old_search_index_path
    internal.search_docs_loader = old_search_docs_loader


@pytest.fixture
def no_search_index_path() -> Generator[None, None, None]:
    old_search_index_path = config.SETTINGS.main.docs_index_path
    old_search_docs_loader = internal.search_docs_loader
    config.SETTINGS.main.docs_index_path = get_fixtures_dir() / "docs" / "no-index.json"
    internal.search_docs_loader = internal.SearchDocs()
    yield
    config.SETTINGS.main.docs_index_path = old_search_index_path
    internal.search_docs_loader = old_search_docs_loader


async def test_search_docs(client: TestClient, override_search_index_path: None) -> None:
    with client:
        response = client.get("/api/search/docs?query=guid")

    assert response.status_code == 200
    assert response.json() is not None
    response_json = response.json()
    assert isinstance(response_json, list)
    assert response_json[0]["title"] == "Guides"


async def test_search_docs_limit(client: TestClient, override_search_index_path: None) -> None:
    with client:
        response = client.get("/api/search/docs?query=a&limit=1")

    assert response.status_code == 200
    assert response.json() is not None
    response_json = response.json()
    assert isinstance(response_json, list)
    assert len(response_json) == 1


async def test_no_search_docs(client: TestClient, no_search_index_path: None) -> None:
    with client:
        response = client.get("/api/search/docs?query=guid")

    assert response.status_code == 404
    assert response.json() is not None
    response_json = response.json()
    assert response_json == {
        "data": None,
        "errors": [{"message": "documentation index not found", "extensions": {"code": 404}}],
    }


@pytest.fixture
def recorder_bus(helper: TestHelper, dependency_provider: Provider) -> Generator[Any, None, None]:
    original = config.OVERRIDE.message_bus
    bus = helper.get_message_bus_recorder()
    config.OVERRIDE.message_bus = bus
    with dependency_provider.scope(build_message_bus, lambda: bus):
        yield bus
    config.OVERRIDE.message_bus = original


async def test_response_delay_endpoint_broadcasts(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers: dict[str, str],
    default_branch: Branch,
    register_core_models_schema: None,
    create_test_admin: Node,
    recorder_bus: Any,
) -> None:
    with client:
        response = client.post("/api/response-delay", headers=admin_headers, json={"response_delay": 1})

    assert response.status_code == 200
    assert response.json() == {"response_delay": 1}

    published = recorder_bus.messages_per_routing_key.get("refresh.settings.response_delay")
    assert published
    assert published[0].response_delay == 1


async def test_response_delay_endpoint_requires_super_admin(
    db: InfrahubDatabase,
    client: TestClient,
    client_headers: dict[str, str],
    default_branch: Branch,
    register_core_models_schema: None,
) -> None:
    with client:
        response = client.post("/api/response-delay", headers=client_headers, json={"response_delay": 1})

    assert response.status_code in (401, 403)


async def test_response_delay_message_updates_settings() -> None:
    original = config.SETTINGS.miscellaneous.response_delay
    try:
        await refresh_settings.response_delay(message=RefreshSettingsResponseDelay(response_delay=2))
        assert config.SETTINGS.miscellaneous.response_delay == 2
    finally:
        config.SETTINGS.miscellaneous.response_delay = original
