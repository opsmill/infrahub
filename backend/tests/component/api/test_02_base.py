from fastapi.testclient import TestClient

from infrahub.core.branch import Branch
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase


async def test_get_invalid(
    client: TestClient, db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    with client:
        response = client.get("/api/so-such-route")

    assert response.status_code == 404
    assert response.json()
    assert response.json()["errors"]
    assert response.json()["errors"] == [
        {"message": "The requested endpoint /api/so-such-route does not exist", "extensions": {"code": 404}}
    ]
