import pytest

from infrahub import config
from infrahub.database import InfrahubDatabase


async def test_config_endpoint(
    db: InfrahubDatabase, client, client_headers, default_branch, register_core_models_schema: None
):
    with client:
        response = client.get("/api/config", headers=client_headers)

    assert response.status_code == 200
    assert response.json() is not None

    result = response.json()

    assert sorted(result.keys()) == ["analytics", "experimental_features", "logging", "main", "sso"]


@pytest.mark.parametrize("allow_anonymous_access", [False, True])
async def test_config_endpoint_anonymous_account(
    db: InfrahubDatabase, client, default_branch, register_core_models_schema: None, allow_anonymous_access: bool
):
    config.SETTINGS.main.allow_anonymous_access = allow_anonymous_access

    with client:
        response = client.get("/api/config")

    assert response.status_code == 200 if allow_anonymous_access else 401


async def test_info_endpoint(
    db: InfrahubDatabase, client, client_headers, default_branch, register_core_models_schema: None
):
    with client:
        response = client.get("/api/info", headers=client_headers)

    assert response.status_code == 200
    assert response.json() is not None

    result = response.json()

    assert sorted(result.keys()) == ["deployment_id", "version"]


@pytest.mark.parametrize("allow_anonymous_access", [False, True])
async def test_info_endpoint_anonymous_account(
    db: InfrahubDatabase, client, default_branch, register_core_models_schema: None, allow_anonymous_access: bool
):
    config.SETTINGS.main.allow_anonymous_access = allow_anonymous_access

    with client:
        response = client.get("/api/info")

    assert response.status_code == 200 if allow_anonymous_access else 401
