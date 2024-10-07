from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import create_default_menu
from infrahub.core.protocols import CoreMenuItem
from infrahub.core.schema import SchemaRoot
from infrahub.database import InfrahubDatabase
from infrahub.menu.constants import MenuSection
from infrahub.menu.generator import generate_menu
from infrahub.menu.models import MenuItemDefinition


async def test_generate_menu(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema_generics: SchemaRoot,
):
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)

    schema_electriccar = schema_branch.get(name="TestElectricCar")
    schema_electriccar.menu_placement = "Builtin:ObjectManagement"
    schema_branch.set(name="TestElectricCar", schema=schema_electriccar)

    await create_default_menu(db=db)

    new_menu_items = [
        MenuItemDefinition(
            namespace="Test",
            name="CarGaz",
            label="Car Gaz",
            kind="TestCarGaz",
            section=MenuSection.OBJECT,
            order_weight=1500,
        )
    ]

    for item in new_menu_items:
        obj = await item.to_node(db=db)
        await obj.save(db=db)

    menu_items = await registry.manager.query(
        db=db, schema=CoreMenuItem, branch=default_branch, prefetch_relationships=True
    )
    menu = await generate_menu(db=db, branch=default_branch, menu_items=menu_items)

    assert menu
    assert "Test:CarGaz" in menu.data.keys()
