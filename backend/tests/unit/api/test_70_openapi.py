from fastapi.testclient import TestClient

from infrahub.core.branch import Branch


async def test_openapi(client: TestClient, default_branch: Branch, register_core_models_schema: None) -> None:
    """Validate that the OpenAPI specs can be generated."""
    with client:
        response = client.get("/api/openapi.json")

    assert response.status_code == 200
    assert response.json() is not None
