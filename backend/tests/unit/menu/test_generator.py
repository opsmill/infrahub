from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import create_default_menu
from infrahub.core.protocols import CoreMenuItem
from infrahub.core.schema import SchemaRoot
from infrahub.database import InfrahubDatabase
from infrahub.menu.constants import FULL_DEFAULT_MENU, MenuSection
from infrahub.menu.generator import generate_menu
from infrahub.menu.models import MenuItemDefinition
from infrahub.menu.utils import create_menu_children


def generate_menu_fixtures(prefix: str = "Menu", depth: int = 1, nbr_item: int = 10) -> list[MenuItemDefinition]:
    max_depth = 3
    next_level_item: int = 3

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


async def test_generate_menu_placement(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema_generics: SchemaRoot,
    helper,
):
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)

    schema_car = schema_branch.get(name="TestCar")
    schema_car.menu_placement = "BuiltinObjectManagement"
    schema_branch.set(name="TestCar", schema=schema_car)

    await create_default_menu(db=db)

    new_menu_items = generate_menu_fixtures(nbr_item=2)

    for item in new_menu_items:
        obj = await item.to_node(db=db)
        await obj.save(db=db)
        if item.children:
            await create_menu_children(db=db, parent=obj, children=item.children)

    menu_items = await registry.manager.query(db=db, schema=CoreMenuItem, branch=default_branch)
    menu = await generate_menu(db=db, branch=default_branch, menu_items=menu_items)

    assert menu
    assert "TestMenu0" in menu.data.keys()
    assert "BuiltinObjectManagement" in menu.data.keys()
    assert "TestCar" in menu.data["BuiltinObjectManagement"].children.keys()


async def test_generate_menu_top_level(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema_generics: SchemaRoot,
    helper,
):
    await create_default_menu(db=db)

    new_menu_items = generate_menu_fixtures(nbr_item=2)

    for item in new_menu_items:
        obj = await item.to_node(db=db)
        await obj.save(db=db)
        if item.children:
            await create_menu_children(db=db, parent=obj, children=item.children)

    menu_items = await registry.manager.query(db=db, schema=CoreMenuItem, branch=default_branch)
    menu = await generate_menu(db=db, branch=default_branch, menu_items=menu_items)

    assert menu
    assert "TestMenu0" in menu.data.keys()
    assert "TestCar" in menu.data.keys()


async def test_generate_menu_default(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema_generics: SchemaRoot,
    helper,
):
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    schema_car = schema_branch.get(name="TestCar")
    schema_car.menu_placement = "DoesNotExist"
    schema_branch.set(name="TestCar", schema=schema_car)

    await create_default_menu(db=db)

    new_menu_items = generate_menu_fixtures(nbr_item=2)

    for item in new_menu_items:
        obj = await item.to_node(db=db)
        await obj.save(db=db)
        if item.children:
            await create_menu_children(db=db, parent=obj, children=item.children)

    menu_items = await registry.manager.query(db=db, schema=CoreMenuItem, branch=default_branch)
    menu = await generate_menu(db=db, branch=default_branch, menu_items=menu_items)

    assert menu
    assert "TestMenu0" in menu.data.keys()
    assert "TestCar" in menu.data[FULL_DEFAULT_MENU].children.keys()
