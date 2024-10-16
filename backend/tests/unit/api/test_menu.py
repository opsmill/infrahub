from infrahub.core.branch import Branch
from infrahub.core.initialization import create_default_menu
from infrahub.core.schema import SchemaRoot
from infrahub.database import InfrahubDatabase


async def test_get_menu(
    db: InfrahubDatabase,
    client,
    client_headers,
    default_branch: Branch,
    car_person_schema_generics: SchemaRoot,
    car_person_data_generic,
):
    await create_default_menu(db=db)

    with client:
        response = client.get(
            "/api/menu",
            headers=client_headers,
        )

    assert response.status_code == 200
    assert response.json() is not None
