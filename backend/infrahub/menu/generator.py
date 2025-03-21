from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.protocols import CoreMenuItem
from infrahub.log import get_logger

from .constants import FULL_DEFAULT_MENU
from .models import MenuDict, MenuItemDict

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.permissions import PermissionManager

log = get_logger()


def get_full_name(obj: CoreMenuItem) -> str:
    return f"{obj.namespace.value}{obj.name.value}"


async def generate_restricted_menu(
    db: InfrahubDatabase, branch: Branch, menu_items: list[CoreMenuItem], account_permissions: PermissionManager | None
) -> MenuDict:
    menu = await generate_menu(db=db, branch=branch, menu_items=menu_items)

    for item in menu.data.values():
        has_permission = True
        for permission in item.get_global_permissions():
            has_permission = account_permissions is not None and account_permissions.has_permission(
                permission=permission
            )

        if not has_permission:
            item.hidden = True

    return menu


async def generate_menu(db: InfrahubDatabase, branch: Branch, menu_items: list[CoreMenuItem]) -> MenuDict:
    structure = MenuDict()
    full_schema = registry.schema.get_full(branch=branch, duplicate=False)

    already_processed = []

    # Process the parent first
    for item in menu_items:
        full_name = get_full_name(item)
        parent1 = await item.parent.get_peer(db=db, peer_type=CoreMenuItem)
        if parent1:
            continue
        structure.data[full_name] = MenuItemDict.from_node(obj=item)
        already_processed.append(full_name)

    # Process the children
    havent_been_processed: list[str] = []
    for item in menu_items:
        full_name = get_full_name(item)
        if full_name in already_processed:
            continue

        parent2 = await item.parent.get_peer(db=db, peer_type=CoreMenuItem)
        if not parent2:
            havent_been_processed.append(full_name)
            continue

        parent_full_name = get_full_name(parent2)
        menu_item = structure.find_item(name=parent_full_name)
        if menu_item:
            child_item = MenuItemDict.from_node(obj=item)
            menu_item.children[str(child_item.identifier)] = child_item
        else:
            log.warning(
                "new_menu_request: unable to find the parent menu item",
                branch=branch.name,
                menu_item=full_name,
                parent_item=parent_full_name,
            )

    items_to_add = {schema.kind: False for schema in full_schema.values() if schema.include_in_menu is True}

    nbr_remaining_items_last_round = len(items_to_add.values())
    nbr_remaining_items = len([value for value in items_to_add.values() if value is False])
    while not all(items_to_add.values()):
        for item_name, already_done in items_to_add.items():
            if already_done:
                continue

            schema = full_schema[item_name]
            menu_item = MenuItemDict.from_schema(model=schema)
            already_in_schema = bool(structure.find_item(name=str(menu_item.identifier)))
            if already_in_schema:
                items_to_add[item_name] = True
                continue

            if not schema.menu_placement:
                first_element = MenuItemDict.from_schema(model=schema)
                first_element.name = f"{first_element.name}Sub"
                first_element.order_weight = 1
                menu_item.children[str(first_element.identifier)] = first_element
                structure.data[str(menu_item.identifier)] = menu_item
                items_to_add[item_name] = True
            elif menu_placement := structure.find_item(name=schema.menu_placement):
                menu_placement.children[str(menu_item.identifier)] = menu_item
                items_to_add[item_name] = True
                continue

        nbr_remaining_items = len([value for value in items_to_add.values() if value is False])
        if nbr_remaining_items_last_round == nbr_remaining_items:
            break
        nbr_remaining_items_last_round = nbr_remaining_items

    # ----------------------------------------------------------------------------
    # Assign the remaining items for which we couldn't find the menu_placement to the default menu
    # ----------------------------------------------------------------------------
    default_menu = structure.find_item(name=FULL_DEFAULT_MENU)
    if not default_menu:
        raise ValueError("Unable to locate the default menu item")

    for item_name, already_done in items_to_add.items():
        if already_done:
            continue
        schema = full_schema[item_name]
        menu_item = MenuItemDict.from_schema(model=schema)
        log.warning(
            "new_menu_request: unable to find the menu_placement defined in the schema",
            branch=branch.name,
            item=schema.kind,
            menu_placement=schema.menu_placement,
        )
        default_menu.children[str(menu_item.identifier)] = menu_item
        items_to_add[item_name] = True

    return structure
