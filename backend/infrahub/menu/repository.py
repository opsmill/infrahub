from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreMenuItem
from infrahub.database import InfrahubDatabase

from .models import MenuDict, MenuItemDefinition, MenuItemDict


class MenuRepository:
    def __init__(self, db: InfrahubDatabase):
        self.db = db

    async def get_menu(self, nodes: dict[str, CoreMenuItem] | None = None) -> MenuDict:
        menu_nodes = nodes or await self.get_menu_db()
        return await self._convert_menu_from_db(nodes=menu_nodes)

    async def _convert_menu_from_db(self, nodes: dict[str, CoreMenuItem]) -> MenuDict:
        menu = MenuDict()
        menu_by_ids = {menu_node.get_id(): MenuItemDict.from_node(menu_node) for menu_node in nodes.values()}

        async def add_children(menu_item: MenuItemDict, menu_node: CoreMenuItem) -> MenuItemDict:
            children = await menu_node.children.get_peers(db=self.db, peer_type=CoreMenuItem)
            for child_id, child_node in children.items():
                if child_menu_item := menu_by_ids.get(child_id):
                    child = await add_children(child_menu_item, child_node)
                    menu_item.children[str(child.identifier)] = child
            return menu_item

        for menu_node in nodes.values():
            menu_item = menu_by_ids[menu_node.get_id()]
            parent = await menu_node.parent.get_peer(db=self.db, peer_type=CoreMenuItem)
            if parent:
                continue

            children = await menu_node.children.get_peers(db=self.db, peer_type=CoreMenuItem)
            for child_id, child_node in children.items():
                if child_menu_item := menu_by_ids.get(child_id):
                    child = await add_children(child_menu_item, child_node)
                    menu_item.children[str(child.identifier)] = child

            menu.data[str(menu_item.identifier)] = menu_item

        return menu

    async def get_menu_db(self) -> dict[str, CoreMenuItem]:
        menu_nodes = await NodeManager.query(
            schema=CoreMenuItem,
            filters={"namespace__value": "Builtin"},
            prefetch_relationships=True,
            db=self.db,
        )
        return {node.get_id(): node for node in menu_nodes}

    async def create_menu(self, menu: list[MenuItemDefinition]) -> None:
        for item in menu:
            obj = await item.to_node(db=self.db)
            await obj.save(db=self.db)
            if item.children:
                await self.create_menu_children(parent=obj, children=item.children)

    async def create_menu_children(self, parent: CoreMenuItem, children: list[MenuItemDefinition]) -> None:
        for child in children:
            obj = await child.to_node(db=self.db, parent=parent)
            await obj.save(db=self.db)
            if child.children:
                await self.create_menu_children(parent=obj, children=child.children)

    async def update_menu(
        self, existing_menu: MenuDict, new_menu: MenuDict, menu_nodes: dict[str, CoreMenuItem]
    ) -> None:
        async def process_menu_item(menu_item: MenuItemDict, parent: CoreMenuItem | None) -> None:
            existing_item = existing_menu.find_item(name=str(menu_item.identifier))
            if existing_item and existing_item.id:
                node = menu_nodes[existing_item.id]
                await self.update_menu_item(
                    node=node, existing_menu_item=existing_item, new_menu_item=menu_item, parent=parent
                )
            else:
                node = await self.create_menu_item(new_menu_item=menu_item, parent=parent)

            for child_item in menu_item.children.values():
                await process_menu_item(menu_item=child_item, parent=node)

        for top_level_item in new_menu.data.values():
            await process_menu_item(menu_item=top_level_item, parent=None)

        # Delete items that are not in the new menu
        menu_to_delete = existing_menu.get_all_identifiers() - new_menu.get_all_identifiers()
        for item_to_delete in menu_to_delete:
            existing_item = existing_menu.find_item(name=item_to_delete)
            if existing_item and existing_item.id:
                node = menu_nodes[existing_item.id]
                await node.delete(db=self.db)

    async def update_menu_item(
        self,
        node: CoreMenuItem,
        existing_menu_item: MenuItemDict,
        new_menu_item: MenuItemDict,
        parent: CoreMenuItem | None,
    ) -> None:
        attrs_to_update = existing_menu_item.diff_attributes(new_menu_item)
        for attr_name, value in attrs_to_update.items():
            attr = getattr(node, attr_name)
            attr.value = value
        await node.parent.update(data=parent, db=self.db)  # type: ignore[arg-type]
        await node.save(db=self.db)

    async def create_menu_item(self, new_menu_item: MenuItemDict, parent: CoreMenuItem | None) -> CoreMenuItem:
        obj = await new_menu_item.to_node(db=self.db, parent=parent)
        await obj.save(db=self.db)
        return obj
