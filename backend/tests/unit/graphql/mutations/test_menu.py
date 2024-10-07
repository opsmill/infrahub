from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.menu.constants import MenuSection
from infrahub.menu.models import MenuItem
from infrahub.services import InfrahubServices
from tests.helpers.graphql import graphql_mutation

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


async def test_menu_create(db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch):
    service = InfrahubServices(database=db)

    CREATE_MENU = """
    mutation CoreMenuItemCreate {
        CoreMenuItemCreate(
            data: {
                namespace: { value: "Builtin" }
                name: { value: "TestCar" }
            }
        ) {
            ok
        }
    }
    """

    result = await graphql_mutation(
        query=CREATE_MENU,
        db=db,
        service=service,
    )
    assert "Builtin is not valid" in result.errors[0].args[0]


async def test_menu_update_protected(db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch):
    service = InfrahubServices(database=db)

    menu_item = MenuItem(
        namespace="Builtin",
        name="Branches",
        label="Branches",
        path="/branche",
        icon="mdi:layers-triple",
        protected=True,
        section=MenuSection.INTERNAL,
        order_weight=1000,
    )
    obj = await menu_item.to_node(db=db)
    await obj.save(db=db)

    UPDATE_MENU = """
    mutation CoreMenuItemUpdate($id: String!) {
        CoreMenuItemUpdate(
            data: {
                id: $id
                name: { value: "TestCar" }
            }
        ) {
            ok
        }
    }
    """

    result = await graphql_mutation(
        query=UPDATE_MENU,
        db=db,
        variables={"id": obj.id},
        service=service,
    )

    assert result.errors
    assert "This object is protected" in result.errors[0].args[0]


async def test_menu_delete_protected(db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch):
    service = InfrahubServices(database=db)

    menu_item = MenuItem(
        namespace="Builtin",
        name="Branches",
        label="Branches",
        path="/branche",
        icon="mdi:layers-triple",
        protected=True,
        section=MenuSection.INTERNAL,
        order_weight=1000,
    )
    obj = await menu_item.to_node(db=db)
    await obj.save(db=db)

    DELETE_MENU = """
    mutation CoreMenuItemDelete($id: String!) {
        CoreMenuItemDelete(
            data: {
                id: $id
            }
        ) {
            ok
        }
    }
    """

    result = await graphql_mutation(
        query=DELETE_MENU,
        db=db,
        variables={"id": obj.id},
        service=service,
    )

    assert result.errors
    assert "This object is protected" in result.errors[0].args[0]
