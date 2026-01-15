from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import create_default_menu
from infrahub.core.protocols import CoreMenuItem
from infrahub.core.schema import NodeSchema, SchemaRoot
from infrahub.database import InfrahubDatabase
from infrahub.menu.constants import FULL_DEFAULT_MENU, MenuSection
from infrahub.menu.generator import generate_menu
from infrahub.menu.models import MenuItemDefinition
from infrahub.menu.repository import MenuRepository


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
    menu_repository: MenuRepository,
    helper,
) -> None:
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)

    schema_car = schema_branch.get(name="TestCar")
    schema_car.menu_placement = "BuiltinObjectManagement"
    schema_branch.set(name="TestCar", schema=schema_car)

    await create_default_menu(db=db)

    new_menu_items = generate_menu_fixtures(nbr_item=2)
    await menu_repository.create_menu(menu=new_menu_items)

    menu_items = await registry.manager.query(db=db, schema=CoreMenuItem, branch=default_branch)
    menu = await generate_menu(db=db, branch=default_branch, menu_items=menu_items)

    assert menu
    assert "TestMenu0" in menu.data.keys()
    assert "BuiltinObjectManagement" in menu.data.keys()
    assert "TestCar" in menu.data["BuiltinObjectManagement"].children.keys()


async def test_generate_menu_top_level(
    db: InfrahubDatabase,
    menu_repository: MenuRepository,
    default_branch: Branch,
    car_person_schema_generics: SchemaRoot,
    helper,
) -> None:
    await create_default_menu(db=db)

    new_menu_items = generate_menu_fixtures(nbr_item=2)
    await menu_repository.create_menu(menu=new_menu_items)

    menu_items = await registry.manager.query(db=db, schema=CoreMenuItem, branch=default_branch)
    menu = await generate_menu(db=db, branch=default_branch, menu_items=menu_items)

    assert menu
    assert "TestMenu0" in menu.data.keys()
    assert "TestCar" in menu.data.keys()
    assert "TestCarSub" in menu.data["TestCar"].children.keys()


async def test_generate_menu_default(
    db: InfrahubDatabase,
    menu_repository: MenuRepository,
    default_branch: Branch,
    car_person_schema_generics: SchemaRoot,
    helper,
) -> None:
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    schema_car = schema_branch.get(name="TestCar")
    schema_car.menu_placement = "DoesNotExist"
    schema_branch.set(name="TestCar", schema=schema_car)

    await create_default_menu(db=db)

    new_menu_items = generate_menu_fixtures(nbr_item=2)
    await menu_repository.create_menu(menu=new_menu_items)

    menu_items = await registry.manager.query(db=db, schema=CoreMenuItem, branch=default_branch)
    menu = await generate_menu(db=db, branch=default_branch, menu_items=menu_items)

    assert menu
    assert "TestMenu0" in menu.data.keys()
    assert "TestCar" in menu.data[FULL_DEFAULT_MENU].children.keys()


async def test_generate_ipam_menu(
    db: InfrahubDatabase,
    menu_repository: MenuRepository,
    default_branch: Branch,
    car_person_schema_generics: SchemaRoot,
) -> None:
    """Validate that the IPAM menu only shows up if IP nodes are defined in the schema"""
    await create_default_menu(db=db)

    new_menu_items = generate_menu_fixtures(nbr_item=2)
    await menu_repository.create_menu(menu=new_menu_items)

    menu_items = await registry.manager.query(db=db, schema=CoreMenuItem, branch=default_branch)
    initial_menu = await generate_menu(db=db, branch=default_branch, menu_items=menu_items)

    schema = SchemaRoot(
        nodes=[
            NodeSchema(
                name="IPAddress",
                namespace="Test",
                inherit_from=["BuiltinIPAddress"],
            )
        ]
    )
    registry.schema.register_schema(schema=schema, branch=default_branch.name)

    updated_menu = await generate_menu(db=db, branch=default_branch, menu_items=menu_items)

    assert "BuiltinIPAM" not in initial_menu.data
    assert "BuiltinIPAM" in updated_menu.data
