from collections.abc import Generator
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from infrahub import config
from infrahub.api import internal
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.preferences.constants import GLOBAL_OWNER_ID
from infrahub.core.preferences.models import Preference
from infrahub.core.preferences.repository import PreferenceRepository
from infrahub.database import InfrahubDatabase
from infrahub.instance_identity import InstanceColor
from infrahub.message_bus.messages import RefreshSettingsResponseDelay
from infrahub.message_bus.operations.refresh import settings as refresh_settings
from tests.adapters.message_bus import BusRecorder
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
        "instance",
        "instance_defaults",
        "ldap",
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config.SETTINGS.main, "allow_anonymous_access", allow_anonymous_access)

    with client:
        response = client.get("/api/config")

    assert response.status_code == 200
    assert response.json()["instance"] == {"label": None, "color": None}
    assert response.json()["instance_defaults"] == {"label": None, "color": None}
    assert await PreferenceRepository(db=db).get_all() == []


@dataclass
class DeploymentDefaultCase:
    name: str
    saved: Preference | None
    expected: dict[str, str | None]


DEPLOYMENT_DEFAULT_CASES: list[DeploymentDefaultCase] = [
    DeploymentDefaultCase(
        name="no_saved_row_serves_the_defaults",
        saved=None,
        expected={"label": "staging", "color": "AMBER"},
    ),
    DeploymentDefaultCase(
        name="saved_row_without_identity_serves_the_defaults",
        saved=Preference(owner_id=GLOBAL_OWNER_ID, timezone="UTC"),
        expected={"label": "staging", "color": "AMBER"},
    ),
    DeploymentDefaultCase(
        name="saved_values_override_the_defaults",
        saved=Preference(owner_id=GLOBAL_OWNER_ID, instance_label="us-east-1 PROD", instance_color=InstanceColor.RED),
        expected={"label": "us-east-1 PROD", "color": "RED"},
    ),
    DeploymentDefaultCase(
        name="saved_label_with_default_color",
        saved=Preference(owner_id=GLOBAL_OWNER_ID, instance_label="us-east-1 PROD"),
        expected={"label": "us-east-1 PROD", "color": "AMBER"},
    ),
    DeploymentDefaultCase(
        name="saved_color_with_default_label",
        saved=Preference(owner_id=GLOBAL_OWNER_ID, instance_color=InstanceColor.RED),
        expected={"label": "staging", "color": "RED"},
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in DEPLOYMENT_DEFAULT_CASES])
async def test_config_endpoint_resolves_each_identity_field_over_the_deployment_default(
    db: InfrahubDatabase,
    client: TestClient,
    default_branch: Branch,
    register_core_models_schema: None,
    monkeypatch: pytest.MonkeyPatch,
    case: DeploymentDefaultCase,
) -> None:
    monkeypatch.setattr(config.SETTINGS.instance, "label", "staging")
    monkeypatch.setattr(config.SETTINGS.instance, "color", InstanceColor.AMBER)
    if case.saved is not None:
        await PreferenceRepository(db=db).save(case.saved)

    with client:
        response = client.get("/api/config")

    assert response.status_code == 200
    assert response.json()["instance"] == case.expected
    assert response.json()["instance_defaults"] == {"label": "staging", "color": "AMBER"}


SET_INSTANCE_IDENTITY = """
mutation ($instance_label: String, $instance_color: InstanceColor) {
  InfrahubSetPreferences(scope: GLOBAL, instance_label: $instance_label, instance_color: $instance_color) {
    ok
  }
}
"""


async def test_config_endpoint_serves_the_deployment_defaults_again_after_a_reset(
    client: TestClient,
    admin_headers: dict[str, str],
    default_branch: Branch,
    register_core_models_schema: None,
    create_test_admin: Node,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config.SETTINGS.instance, "label", "staging")
    monkeypatch.setattr(config.SETTINGS.instance, "color", InstanceColor.AMBER)

    with client:
        saved = client.post(
            "/graphql",
            json={"query": SET_INSTANCE_IDENTITY, "variables": {"instance_label": "PROD", "instance_color": "RED"}},
            headers=admin_headers,
        )
        while_saved = client.get("/api/config")
        reset = client.post(
            "/graphql",
            json={"query": SET_INSTANCE_IDENTITY, "variables": {"instance_label": None, "instance_color": None}},
            headers=admin_headers,
        )
        after_reset = client.get("/api/config")

    assert saved.json() == {"data": {"InfrahubSetPreferences": {"ok": True}}}
    assert while_saved.json()["instance"] == {"label": "PROD", "color": "RED"}
    assert reset.json() == {"data": {"InfrahubSetPreferences": {"ok": True}}}
    assert after_reset.json()["instance"] == {"label": "staging", "color": "AMBER"}


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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config.SETTINGS.main, "allow_anonymous_access", allow_anonymous_access)

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


async def test_response_delay_endpoint_broadcasts(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers: dict[str, str],
    default_branch: Branch,
    register_core_models_schema: None,
    create_test_admin: Node,
    recorder_bus: BusRecorder,
) -> None:
    with client:
        response = client.post("/api/response-delay", headers=admin_headers, json={"response_delay": 1})

    assert response.status_code == 200
    assert response.json() == {"response_delay": 1}

    published = recorder_bus.messages_per_routing_key.get("refresh.settings.response_delay")
    assert published
    assert isinstance(published[0], RefreshSettingsResponseDelay)
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
