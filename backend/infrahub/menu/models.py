from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field
from typing_extensions import Self

from infrahub.core.account import GlobalPermission
from infrahub.core.node import Node
from infrahub.core.protocols import CoreMenuItem
from infrahub.core.schema import GenericSchema, MainSchemaTypes, NodeSchema, ProfileSchema

from .constants import MenuSection

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


def get_full_name(obj: CoreMenuItem | NodeSchema | GenericSchema | ProfileSchema) -> str:
    if isinstance(obj, (NodeSchema, GenericSchema, ProfileSchema)):
        return _get_full_name_schema(obj)
    return _get_full_name_node(obj)


def _get_full_name_node(obj: CoreMenuItem) -> str:
    return f"{obj.namespace.value}{obj.name.value}"


def _get_full_name_schema(node: MainSchemaTypes) -> str:
    return f"{node.namespace}{node.name}"


@dataclass
class MenuDict:
    data: dict[str, MenuItemDict] = field(default_factory=dict)

    def find_item(self, name: str) -> MenuItemDict | None:
        return self._find_child_item(name=name, children=self.data)

    @classmethod
    def _find_child_item(cls, name: str, children: dict[str, MenuItemDict]) -> MenuItemDict | None:
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
        data: dict[str, list[MenuItemList]] = {}

        for section in [MenuSection.INTERNAL, MenuSection.OBJECT]:
            item_per_section = [
                value.to_list() for value in self.data.values() if value.section == section and value.hidden is False
            ]
            data[section.value] = sorted(item_per_section, key=lambda d: d.order_weight)

        return Menu(sections=data)

    # @staticmethod
    # def _sort_menu_items(items: dict[str, MenuItem]) -> dict[str, MenuItem]:
    #     sorted_dict = dict(sorted(items.items(), key=lambda x: (x[1].order_weight, x[0]), reverse=False))
    #     return sorted_dict


@dataclass
class Menu:
    sections: dict[str, list[MenuItemList]] = field(default_factory=dict)


class MenuItem(BaseModel):
    identifier: str = Field(..., description="Unique identifier for this menu item")
    label: str = Field(..., description="Title of the menu item")
    path: str = Field(default="", description="URL endpoint if applicable")
    icon: str = Field(default="", description="The icon to show for the current view")
    kind: str = Field(default="", description="Kind of the model associated with this menuitem if applicable")
    order_weight: int = 5000
    section: MenuSection = MenuSection.OBJECT
    permissions: list[str] = Field(default_factory=list)

    @classmethod
    def from_node(cls, obj: CoreMenuItem) -> Self:
        return cls(
            identifier=get_full_name(obj),
            label=obj.label.value or "",
            icon=obj.icon.value or "",
            order_weight=obj.order_weight.value,
            path=obj.path.value or "",
            kind=obj.kind.value or "",
            section=obj.section.value,
            permissions=obj.required_permissions.value or [],
        )

    @classmethod
    def from_schema(cls, model: NodeSchema | GenericSchema | ProfileSchema) -> Self:
        return cls(
            identifier=get_full_name(model),
            label=model.label or model.kind,
            path=f"/objects/{model.kind}",
            icon=model.icon or "",
            kind=model.kind,
        )


class MenuItemDict(MenuItem):
    hidden: bool = False
    children: dict[str, MenuItemDict] = Field(default_factory=dict, description="Child objects")

    def to_list(self) -> MenuItemList:
        data = self.model_dump(exclude={"children"})
        unsorted_children = [child.to_list() for child in self.children.values() if child.hidden is False]
        data["children"] = sorted(unsorted_children, key=lambda d: d.order_weight)
        return MenuItemList(**data)

    def get_global_permissions(self) -> list[GlobalPermission]:
        permissions: list[GlobalPermission] = []
        for permission in self.permissions:
            if not permission.startswith("global"):
                continue
            permissions.append(GlobalPermission.from_string(input=permission))
        return permissions


class MenuItemList(MenuItem):
    children: list[MenuItemList] = Field(default_factory=list, description="Child objects")


class MenuItemDefinition(BaseModel):
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
    permissions: list[str] = Field(default_factory=list)
    children: list[MenuItemDefinition] = Field(default_factory=list)

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
            required_permissions=self.permissions,
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
        return f"{self.namespace}{self.name}"
