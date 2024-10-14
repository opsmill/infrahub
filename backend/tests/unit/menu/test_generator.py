from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import create_default_menu
from infrahub.core.protocols import CoreMenuItem
from infrahub.core.schema import SchemaRoot
from infrahub.database import InfrahubDatabase
from infrahub.menu.constants import MenuSection
from infrahub.menu.generator import generate_menu
from infrahub.menu.models import MenuItemDefinition
from infrahub.menu.utils import create_menu_children


def generate_menu_fixtures(prefix: str = "Menu", depth: int = 1, nbr_item: int = 10) -> list[MenuItemDefinition]:
    max_depth = 3
    next_level_item: int = 5

    menu: list[MenuItemDefinition] = []

    for idx in range(nbr_item):
        item = MenuItemDefinition(
            namespace="Test",
            name=f"{prefix}{idx}",
            label=f"{prefix}{idx}",
            section=MenuSection.OBJECT,
            order_weight=(idx + 1) * 1000,
        )

        if depth <= max_depth:
            item.children = generate_menu_fixtures(prefix=f"{prefix}{idx}", depth=depth + 1, nbr_item=next_level_item)

        menu.append(item)

    return menu


async def test_generate_menu(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema_generics: SchemaRoot,
    helper,
):
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)

    schema_electriccar = schema_branch.get(name="TestElectricCar")
    schema_electriccar.menu_placement = "Builtin:ObjectManagement"
    schema_branch.set(name="TestElectricCar", schema=schema_electriccar)

    await create_default_menu(db=db)

    new_menu_items = generate_menu_fixtures(nbr_item=5)

    for item in new_menu_items:
        obj = await item.to_node(db=db)
        await obj.save(db=db)
        if item.children:
            await create_menu_children(db=db, parent=obj, children=item.children)

    menu_items = await registry.manager.query(
        db=db, schema=CoreMenuItem, branch=default_branch, prefetch_relationships=True
    )
    menu = await generate_menu(db=db, branch=default_branch, menu_items=menu_items)

    assert menu
    assert "Test:Menu0" in menu.data.keys()
