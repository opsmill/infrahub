from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, Field

from infrahub.core.node import Node
from infrahub.core.protocols import CoreMenuItem

from .constants import MenuSection

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.database import InfrahubDatabase


@dataclass
class Menu:
    data: dict[str, NewInterfaceMenu] = field(default_factory=dict)

    def find_item(self, name: str) -> NewInterfaceMenu | None:
        return self._find_child_item(name=name, children=self.data)

    @classmethod
    def _find_child_item(cls, name: str, children: dict[str, NewInterfaceMenu]) -> NewInterfaceMenu | None:
        if name in children.keys():
            return children[name]

        for child in children.values():
            if not child.children:
                continue
            found = cls._find_child_item(name=name, children=child.children)
            if found:
                return found
        return None

    def to_rest(self) -> Menu:
        return Menu(data=self._sort_menu_items(self.data))

    @staticmethod
    def _sort_menu_items(items: dict[str, NewInterfaceMenu]) -> dict[str, NewInterfaceMenu]:
        sorted_dict = dict(sorted(items.items(), key=lambda x: (x[1].order_weight, x[0]), reverse=False))
        return sorted_dict


class NewInterfaceMenu(BaseModel):
    title: str = Field(..., description="Title of the menu item")
    path: str = Field(default="", description="URL endpoint if applicable")
    icon: str = Field(default="", description="The icon to show for the current view")
    children: dict[str, NewInterfaceMenu] = Field(default_factory=dict, description="Child objects")
    kind: str = Field(default="")
    order_weight: int = 5000
    section: MenuSection = MenuSection.OBJECT

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, NewInterfaceMenu):
            raise NotImplementedError
        return self.title < other.title

    @classmethod
    def from_node(cls, obj: CoreMenuItem) -> Self:
        return cls(
            title=obj.label.value or "",
            icon=obj.icon.value or "",
            order_weight=obj.order_weight.value,
            path=obj.path.value or "",
            kind=obj.get_kind(),
            section=obj.section.value,
        )

    @classmethod
    def from_schema(cls, model: MainSchemaTypes) -> Self:
        return cls(
            title=model.label or model.kind, path=f"/objects/{model.kind}", icon=model.icon or "", kind=model.kind
        )


class MenuItem(BaseModel):
    namespace: str
    name: str
    label: str
    description: str = ""
    icon: str = ""
    protected: bool = False
    path: str = ""
    kind: str = ""
    section: MenuSection = MenuSection.OBJECT
    order_weight: int = 2000
    children: list[MenuItem] = Field(default_factory=list)

    async def to_node(self, db: InfrahubDatabase, parent: CoreMenuItem | None = None) -> CoreMenuItem:
        obj = await Node.init(db=db, schema=CoreMenuItem)
        await obj.new(
            db=db,
            namespace=self.namespace,
            name=self.name,
            label=self.label,
            path=self.get_path(),
            description=self.description or None,
            icon=self.icon or None,
            protected=self.protected,
            section=self.section.value,
            order_weight=self.order_weight,
            parent=parent.id if parent else None,
        )
        return obj

    def get_path(self) -> str | None:
        if self.path:
            return self.path

        if self.kind:
            return f"/objects/{self.kind}"

        return None

    @property
    def full_name(self) -> str:
        return f"{self.namespace}:{self.name}"
