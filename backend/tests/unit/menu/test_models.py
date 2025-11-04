from infrahub.menu.models import MenuDict, MenuItemDefinition, MenuItemDict, MenuSection


async def test_menu_item_dict(menu_fixture_01_data: list[MenuItemDefinition]) -> None:
    menu_item = MenuItemDict.from_definition(definition=menu_fixture_01_data[0])
    assert menu_item.identifier == "UserdefinedTest"
    assert menu_item.label == "Test"
    assert menu_item.section == MenuSection.OBJECT
    assert menu_item.order_weight == 12000

    assert menu_item.get_all_identifiers() == {"UserdefinedTest"}


async def test_menu_item_diff_attributes(menu_fixture_01_data: list[MenuItemDefinition]) -> None:
    menu_item = MenuItemDict.from_definition(definition=menu_fixture_01_data[0])
    menu_item_2 = MenuItemDict.from_definition(definition=menu_fixture_01_data[0])
    menu_item_2.label = "Test2"
    assert menu_item.diff_attributes(other=menu_item_2) == {"label": "Test2"}


async def test_menu_dict_from_definitions(menu_fixture_01_data: list[MenuItemDefinition]) -> None:
    menu = MenuDict.from_definition_list(menu_fixture_01_data)
    assert sorted(menu.data.keys()) == [
        "BuiltinDeployment",
        "BuiltinIPAM",
        "BuiltinOther",
        "BuiltinProposedChanges",
        "UserdefinedTest",
    ]


async def test_menu_dict_get_all_identifiers(menu_fixture_01_data: list[MenuItemDefinition]) -> None:
    menu = MenuDict.from_definition_list(menu_fixture_01_data)
    assert menu.get_all_identifiers() == {
        "UserdefinedTest",
        "BuiltinOther",
        "BuiltinTag",
        "BuiltinIPAM",
        "BuiltinIPPrefix",
        "BuiltinIPAddress",
        "BuiltinProposedChanges",
        "BuiltinDeployment",
        "BuiltinArtifactMenu",
        "BuiltinArtifact",
    }


async def test_menu_dict_get_item_location(menu_fixture_01_data: list[MenuItemDefinition]) -> None:
    menu = MenuDict.from_definition_list(menu_fixture_01_data)
    assert menu.get_item_location("BuiltinArtifact") == ["BuiltinDeployment", "BuiltinArtifactMenu"]
    assert menu.get_item_location("UserdefinedTest") == []
