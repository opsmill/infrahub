from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreMenuItem
from infrahub.database import InfrahubDatabase

from .menu import default_menu
from .models import MenuDict, MenuItemDefinition, MenuItemDict


async def create_default_menu(db: InfrahubDatabase) -> None:
    await create_menu(db=db, menu=default_menu)


async def create_menu(db: InfrahubDatabase, menu: list[MenuItemDefinition]) -> None:
    for item in menu:
        obj = await item.to_node(db=db)
        await obj.save(db=db)
        if item.children:
            await create_menu_children(db=db, parent=obj, children=item.children)


async def create_menu_children(db: InfrahubDatabase, parent: CoreMenuItem, children: list[MenuItemDefinition]) -> None:
    for child in children:
        obj = await child.to_node(db=db, parent=parent)
        await obj.save(db=db)
        if child.children:
            await create_menu_children(db=db, parent=obj, children=child.children)


async def get_existing_menu(db: InfrahubDatabase) -> dict[str, CoreMenuItem]:
    menu_nodes = await NodeManager.query(
        schema=CoreMenuItem,
        filters={"namespace__value": "Builtin"},
        prefetch_relationships=True,
        db=db,
    )
    return {node.get_id(): node for node in menu_nodes}


async def update_menu_item(
    db: InfrahubDatabase,
    node: CoreMenuItem,
    existing_menu_item: MenuItemDict,
    new_menu_item: MenuItemDict,
    parent: CoreMenuItem | None,
) -> None:
    attrs_to_update = existing_menu_item.diff_attributes(new_menu_item)
    for attr_name, value in attrs_to_update.items():
        attr = getattr(node, attr_name)
        attr.value = value
    await node.parent.update(data=parent, db=db)  # type: ignore[arg-type]
    await node.save(db=db)


async def create_menu_item(
    db: InfrahubDatabase, new_menu_item: MenuItemDict, parent: CoreMenuItem | None
) -> CoreMenuItem:
    obj = await new_menu_item.to_node(db=db, parent=parent)
    await obj.save(db=db)
    return obj


async def update_menu(
    db: InfrahubDatabase, existing_menu: MenuDict, new_menu: MenuDict, menu_nodes: dict[str, CoreMenuItem]
) -> None:
    async def process_menu_item(menu_item: MenuItemDict, parent: CoreMenuItem | None) -> None:
        existing_item = existing_menu.find_item(name=str(menu_item.identifier))
        if existing_item and existing_item._id:
            node = menu_nodes[existing_item._id]
            await update_menu_item(
                db=db, node=node, existing_menu_item=existing_item, new_menu_item=menu_item, parent=parent
            )
        else:
            node = await create_menu_item(db=db, new_menu_item=menu_item, parent=parent)

        for child_item in menu_item.children.values():
            await process_menu_item(menu_item=child_item, parent=node)

    for top_level_item in new_menu.data.values():
        await process_menu_item(menu_item=top_level_item, parent=None)

    # Delete items that are not in the new menu
    menu_to_delete = existing_menu.get_all_identifiers() - new_menu.get_all_identifiers()
    for item_to_delete in menu_to_delete:
        existing_item = existing_menu.find_item(name=item_to_delete)
        if existing_item and existing_item._id:
            node = menu_nodes[existing_item._id]
            await node.delete(db=db)
