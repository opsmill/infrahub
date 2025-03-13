from deepdiff import DeepDiff

from infrahub.core.branch import Branch
from infrahub.core.schema import SchemaRoot
from infrahub.database import InfrahubDatabase
from infrahub.menu.menu import default_menu
from infrahub.menu.models import MenuDict, MenuItemDefinition
from infrahub.menu.utils import create_menu, get_existing_menu, update_menu


async def test_get_existing_menu(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaRoot,
    menu_fixture_01: list[MenuItemDefinition],
):
    menu_nodes = await get_existing_menu(db=db)
    existing_menu = await MenuDict.from_db(db=db, nodes=list(menu_nodes.values()))
    assert sorted(existing_menu.data.keys()) == [
        "BuiltinDeployment",
        "BuiltinIPAM",
        "BuiltinOther",
        "BuiltinProposedChanges",
    ]
    assert existing_menu.data["BuiltinDeployment"].children["BuiltinArtifactMenu"]
    assert existing_menu.data["BuiltinDeployment"].children["BuiltinArtifactMenu"].children["BuiltinArtifact"]


async def test_update_menu_small_dataset(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaRoot,
    menu_fixture_11_data: list[MenuItemDefinition],
    menu_fixture_12_data: list[MenuItemDefinition],
):
    await create_menu(db=db, menu=menu_fixture_11_data)

    menu_nodes = await get_existing_menu(db=db)
    existing_menu = await MenuDict.from_db(db=db, nodes=list(menu_nodes.values()))

    initial_menu_dict = MenuDict.from_definition_list(menu_fixture_12_data)

    await update_menu(
        db=db,
        existing_menu=existing_menu,
        new_menu=initial_menu_dict,
        menu_nodes=menu_nodes,
    )

    menu_nodes_after = await get_existing_menu(db=db)
    menu_after = await MenuDict.from_db(db=db, nodes=list(menu_nodes_after.values()))

    diff = DeepDiff(initial_menu_dict.to_rest().sections["object"], menu_after.to_rest().sections["object"])
    assert diff == {}


async def test_update_menu_default_menu(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaRoot,
    menu_fixture_02_data: list[MenuItemDefinition],
):
    await create_menu(db=db, menu=menu_fixture_02_data)

    menu_nodes = await get_existing_menu(db=db)
    existing_menu = await MenuDict.from_db(db=db, nodes=list(menu_nodes.values()))

    default_menu_dict = MenuDict.from_definition_list(default_menu)

    await update_menu(
        db=db,
        existing_menu=existing_menu,
        new_menu=default_menu_dict,
        menu_nodes=menu_nodes,
    )

    menu_nodes_after = await get_existing_menu(db=db)
    menu_after = await MenuDict.from_db(db=db, nodes=list(menu_nodes_after.values()))

    diff = DeepDiff(default_menu_dict.to_rest().sections["object"], menu_after.to_rest().sections["object"])
    assert diff == {}
