from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from infrahub.core.constants import MenuSection
from infrahub.core.constants import infrahubkind as InfrahubKind
from infrahub.core.node import Node
from infrahub.core.protocols import CoreMenuItem

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

DEFAULT_MENU = "other"


class MenuItem(BaseModel):
    name: str
    label: str
    description: str = ""
    icon: str = ""
    protected: bool = False
    path: str = ""
    section: MenuSection = MenuSection.OBJECT
    order_weight: int = 2000
    children: list[MenuItem] = Field(default_factory=list)

    async def to_node(self, db: InfrahubDatabase, parent: CoreMenuItem | None = None) -> CoreMenuItem:
        obj = await Node.init(db=db, schema=CoreMenuItem)
        await obj.new(
            db=db,
            name=self.name,
            label=self.label,
            description=self.description,
            icon=self.icon,
            protected=self.protected,
            section=self.section.value,
            parent=parent.id if parent else None,
        )
        return obj


default_menu = [
    MenuItem(
        name=DEFAULT_MENU,
        label=DEFAULT_MENU.title(),
        protected=True,
        section=MenuSection.OBJECT,
    ),
    MenuItem(
        name="object-management",
        label="Object Management",
        protected=True,
        section=MenuSection.INTERNAL,
        order_weight=1000,
    ),
    MenuItem(
        name="change-control",
        label="Change Control",
        protected=True,
        section=MenuSection.INTERNAL,
        order_weight=2000,
    ),
    MenuItem(
        name="unified-storage",
        label="Unified Storage",
        protected=True,
        section=MenuSection.INTERNAL,
        order_weight=3000,
        children=[
            MenuItem(
                name="schema",
                label="Schema",
                path="/schema",
                icon="mdi:file-code",
                protected=True,
                section=MenuSection.INTERNAL,
                order_weight=1000,
            ),
            MenuItem(
                name="repository",
                label="Repository",
                path=f"/objects/{InfrahubKind.GENERICREPOSITORY}",
                icon="",
                protected=True,
                section=MenuSection.INTERNAL,
                order_weight=2000,
            ),
            MenuItem(
                name="graphql-query",
                label="GraphQL Query",
                path=f"/objects/{InfrahubKind.GRAPHQLQUERY}",
                icon="",
                protected=True,
                section=MenuSection.INTERNAL,
                order_weight=3000,
            ),
        ],
    ),
    MenuItem(
        name="admin",
        label="Admin",
        protected=True,
        section=MenuSection.INTERNAL,
        order_weight=3000,
        children=[
            MenuItem(
                name="webhook",
                label="Webhooks",
                protected=True,
                section=MenuSection.INTERNAL,
                order_weight=1000,
            )
        ],
    ),
]
