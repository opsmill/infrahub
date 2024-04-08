from infrahub.api.menu import InterfaceMenu
from infrahub.core.branch import Branch
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
    with client:
        response = client.get(
            "/api/menu",
            headers=client_headers,
        )

    assert response.status_code == 200
    assert response.json() is not None

    menu = [InterfaceMenu(**menu_item) for menu_item in response.json()]
    assert menu[0].title == "Objects"
    assert menu[0].children[0].title == "Car"
