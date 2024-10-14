from infrahub.core.protocols import CoreMenuItem
from infrahub.database import InfrahubDatabase

from .models import MenuItemDefinition


async def create_menu_children(db: InfrahubDatabase, parent: CoreMenuItem, children: list[MenuItemDefinition]) -> None:
    for child in children:
        obj = await child.to_node(db=db, parent=parent)
        await obj.save(db=db)
        if child.children:
            await create_menu_children(db=db, parent=obj, children=child.children)
