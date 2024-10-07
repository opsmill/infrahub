from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.branch import Branch  # noqa: TCH001
from infrahub.core.protocols import CoreMenuItem
from infrahub.log import get_logger

from .constants import FULL_DEFAULT_MENU
from .models import Menu, NewInterfaceMenu

if TYPE_CHECKING:
    from infrahub.auth import AccountSession
    from infrahub.database import InfrahubDatabase

log = get_logger()


def get_full_name(obj: CoreMenuItem) -> str:
    return f"{obj.namespace.value}:{obj.name.value}"


# pylint: disable=too-many-branches
async def generate_menu(
    db: InfrahubDatabase, branch: Branch, menu_items: list[CoreMenuItem], account: AccountSession | None = None
) -> Menu:
    # FIXME temp hack to avoid pylint to complain
    account = account  # noqa: PLW0127

    structure = Menu()
    full_schema = registry.schema.get_full(branch=branch, duplicate=False)

    already_processed = []
    havent_been_processed = []

    # Process the parent first
    for item in menu_items:
        full_name = get_full_name(item)
        parent = await item.parent.get_peer(db=db, peer_type=CoreMenuItem)
        if parent:
            havent_been_processed.append(full_name)
            continue
        structure.data[full_name] = NewInterfaceMenu.from_node(obj=item)
        already_processed.append(full_name)

    # Process the children
    havent_been_processed = []
    for item in menu_items:
        full_name = get_full_name(item)
        if full_name in already_processed:
            continue

        parent = await item.parent.get_peer(db=db, peer_type=CoreMenuItem)
        if not parent:
            havent_been_processed.append(full_name)
            continue

        parent_full_name = get_full_name(parent)
        menu_item = structure.find_item(name=parent_full_name)
        if menu_item:
            menu_item.children[full_name] = NewInterfaceMenu.from_node(obj=item)
        else:
            log.warning(
                "new_menu_request: unable to find the parent menu item",
                branch=branch.name,
                menu_item=item.name.value,
                parent_item=parent.name.value,
            )

    default_menu = structure.find_item(name=FULL_DEFAULT_MENU)
    if not default_menu:
        raise ValueError("Unable to locate the default menu item")

    for schema in full_schema.values():
        if schema.include_in_menu is False:
            continue

        schema_item_full_name = f"{schema.namespace}:{schema.name}"
        already_in_schema = bool(structure.find_item(name=schema_item_full_name))
        if already_in_schema:
            continue

        menu_item = NewInterfaceMenu.from_schema(model=schema)
        if schema.menu_placement:
            menu_placement = structure.find_item(name=schema.menu_placement)

            if menu_placement:
                menu_placement.children[schema_item_full_name] = menu_item
                continue

            log.warning(
                "new_menu_request: unable to find the menu_placement defined in the schema",
                branch=branch.name,
                item=schema.kind,
                menu_placement=schema.menu_placement,
            )

        default_menu.children[schema.kind] = menu_item

    return structure
