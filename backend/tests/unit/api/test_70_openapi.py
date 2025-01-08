import pytest
from fastapi.testclient import TestClient

from infrahub import config
from infrahub.core.branch import Branch


async def test_openapi(client: TestClient, default_branch: Branch, register_core_models_schema: None) -> None:
    """Validate that the OpenAPI specs can be generated."""
    with client:
        response = client.get("/api/openapi.json")

    assert response.status_code == 200
    assert response.json() is not None


@pytest.mark.parametrize("allow_anonymous_access", [False, True])
async def test_openapi_anonymous_account(
    client: TestClient, default_branch: Branch, register_core_models_schema: None, allow_anonymous_access: bool
) -> None:
    """Validate that the OpenAPI specs can be generated."""
    config.SETTINGS.main.allow_anonymous_access = allow_anonymous_access

    with client:
        response = client.get("/api/openapi.json")

    assert response.status_code == 200
    assert response.json() is not None
