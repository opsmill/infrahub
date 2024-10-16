from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.branch import Branch  # noqa: TCH001
from infrahub.core.protocols import CoreMenuItem
from infrahub.log import get_logger

from .constants import FULL_DEFAULT_MENU
from .models import MenuDict, MenuItemDict

if TYPE_CHECKING:
    from infrahub.auth import AccountSession
    from infrahub.database import InfrahubDatabase

log = get_logger()


def get_full_name(obj: CoreMenuItem) -> str:
    return f"{obj.namespace.value}:{obj.name.value}"


# pylint: disable=too-many-branches
async def generate_menu(
    db: InfrahubDatabase, branch: Branch, menu_items: list[CoreMenuItem], account: AccountSession | None = None
) -> MenuDict:
    # FIXME temp hack to avoid pylint to complain
    account = account  # noqa: PLW0127

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
            menu_item.children[child_item.identifier] = child_item
        else:
            log.warning(
                "new_menu_request: unable to find the parent menu item",
                branch=branch.name,
                menu_item=child_item.identifier,
                parent_item=parent_full_name,
            )

    default_menu = structure.find_item(name=FULL_DEFAULT_MENU)
    if not default_menu:
        raise ValueError("Unable to locate the default menu item")

    for schema in full_schema.values():
        if schema.include_in_menu is False:
            continue

        menu_item = MenuItemDict.from_schema(model=schema)
        already_in_schema = bool(structure.find_item(name=menu_item.identifier))
        if already_in_schema:
            continue

        if schema.menu_placement:
            menu_placement = structure.find_item(name=schema.menu_placement)

            if menu_placement:
                menu_placement.children[menu_item.identifier] = menu_item
                continue

            log.warning(
                "new_menu_request: unable to find the menu_placement defined in the schema",
                branch=branch.name,
                item=schema.kind,
                menu_placement=schema.menu_placement,
            )

        default_menu.children[menu_item.identifier] = menu_item

    return structure
