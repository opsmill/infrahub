from deepdiff import DeepDiff

from infrahub.core.branch import Branch
from infrahub.core.schema import SchemaRoot
from infrahub.menu.menu import default_menu
from infrahub.menu.models import MenuDict, MenuItemDefinition
from infrahub.menu.repository import MenuRepository


async def test_get_menu(
    menu_repository: MenuRepository,
    default_branch: Branch,
    register_core_models_schema: SchemaRoot,
    menu_fixture_01: list[MenuItemDefinition],
) -> None:
    existing_menu = await menu_repository.get_menu()

    assert sorted(existing_menu.data.keys()) == [
        "BuiltinDeployment",
        "BuiltinIPAM",
        "BuiltinOther",
        "BuiltinProposedChanges",
    ]
    assert existing_menu.data["BuiltinDeployment"].id
    assert existing_menu.data["BuiltinDeployment"].children["BuiltinArtifactMenu"]
    assert existing_menu.data["BuiltinDeployment"].children["BuiltinArtifactMenu"].id
    assert existing_menu.data["BuiltinDeployment"].children["BuiltinArtifactMenu"].children["BuiltinArtifact"]
    assert existing_menu.data["BuiltinDeployment"].children["BuiltinArtifactMenu"].children["BuiltinArtifact"].id


async def test_update_menu_small_dataset(
    menu_repository: MenuRepository,
    default_branch: Branch,
    register_core_models_schema: SchemaRoot,
    menu_fixture_11_data: list[MenuItemDefinition],
    menu_fixture_12_data: list[MenuItemDefinition],
) -> None:
    await menu_repository.create_menu(menu=menu_fixture_11_data)

    menu_nodes = await menu_repository.get_menu_db()
    existing_menu = await menu_repository.get_menu(nodes=menu_nodes)

    initial_menu_dict = MenuDict.from_definition_list(menu_fixture_12_data)

    await menu_repository.update_menu(
        existing_menu=existing_menu,
        new_menu=initial_menu_dict,
        menu_nodes=menu_nodes,
    )

    menu_after = await menu_repository.get_menu()

    diff = DeepDiff(initial_menu_dict.to_rest().sections["object"], menu_after.to_rest().sections["object"])
    assert diff == {}


async def test_update_menu_default_menu(
    menu_repository: MenuRepository,
    default_branch: Branch,
    register_core_models_schema: SchemaRoot,
    menu_fixture_02_data: list[MenuItemDefinition],
) -> None:
    await menu_repository.create_menu(menu=menu_fixture_02_data)

    menu_nodes = await menu_repository.get_menu_db()
    existing_menu = await menu_repository.get_menu(nodes=menu_nodes)

    default_menu_dict = MenuDict.from_definition_list(default_menu)

    await menu_repository.update_menu(
        existing_menu=existing_menu,
        new_menu=default_menu_dict,
        menu_nodes=menu_nodes,
    )

    menu_after = await menu_repository.get_menu()

    diff = DeepDiff(default_menu_dict.to_rest().sections["object"], menu_after.to_rest().sections["object"])
    assert diff == {}
