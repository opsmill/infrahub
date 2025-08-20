from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, computed_field
from typing_extensions import Self

from infrahub.core.account import GlobalPermission
from infrahub.core.node import Node
from infrahub.core.protocols import CoreMenuItem
from infrahub.core.schema import GenericSchema, MainSchemaTypes, NodeSchema, ProfileSchema, TemplateSchema

from .constants import MenuSection

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


def get_full_name(obj: CoreMenuItem | NodeSchema | GenericSchema | ProfileSchema | TemplateSchema) -> str:
    if isinstance(obj, NodeSchema | GenericSchema | ProfileSchema | TemplateSchema):
        return _get_full_name_schema(obj)
    return _get_full_name_node(obj)


def _get_full_name_node(obj: CoreMenuItem) -> str:
    return f"{obj.namespace.value}{obj.name.value}"


def _get_full_name_schema(node: MainSchemaTypes) -> str:
    return f"{node.namespace}{node.name}"


@dataclass
class MenuDict:
    data: dict[str, MenuItemDict] = field(default_factory=dict)

    def get_item_location(self, name: str) -> list[str]:
        location, _ = self._find_child_item(name=name, children=self.data)
        return location

    def find_item(self, name: str) -> MenuItemDict | None:
        _, item = self._find_child_item(name=name, children=self.data)
        return item

    @classmethod
    def _find_child_item(cls, name: str, children: dict[str, MenuItemDict]) -> tuple[list[str], MenuItemDict | None]:
        if name in children.keys():
            return [], children[name]

        for child in children.values():
            if not child.children:
                continue
            position, found = cls._find_child_item(name=name, children=child.children)
            if found:
                return [str(child.identifier)] + position, found
        return [], None

    def to_rest(self) -> Menu:
        data: dict[str, list[MenuItemList]] = {}

        for section in [MenuSection.INTERNAL, MenuSection.OBJECT]:
            item_per_section = [
                value.to_list() for value in self.data.values() if value.section == section and value.hidden is False
            ]
            data[section.value] = sorted(item_per_section, key=lambda d: d.order_weight)

        return Menu(sections=data)

    @classmethod
    def from_definition_list(cls, definitions: list[MenuItemDefinition]) -> Self:
        menu = cls()
        for definition in definitions:
            menu.data[definition.full_name] = MenuItemDict.from_definition(definition=definition)
        return menu

    def get_all_identifiers(self) -> set[str]:
        return {identifier for item in self.data.values() for identifier in item.get_all_identifiers()}


@dataclass
class Menu:
    sections: dict[str, list[MenuItemList]] = field(default_factory=dict)


class MenuItem(BaseModel):
    id: str | None = None
    namespace: str = Field(..., description="Namespace of the menu item")
    name: str = Field(..., description="Name of the menu item")
    description: str = Field(default="", description="Description of the menu item")
    protected: bool = Field(default=False, description="Whether the menu item is protected")
    label: str = Field(..., description="Title of the menu item")
    path: str = Field(default="", description="URL endpoint if applicable")
    icon: str = Field(default="", description="The icon to show for the current view")
    kind: str = Field(default="", description="Kind of the model associated with this menuitem if applicable")
    order_weight: int = 5000
    section: MenuSection = MenuSection.OBJECT
    permissions: list[str] = Field(default_factory=list)

    @computed_field
    def identifier(self) -> str:
        return f"{self.namespace}{self.name}"

    def get_path(self) -> str | None:
        if self.path:
            return self.path

        if self.kind:
            return f"/objects/{self.kind}"

        return None

    @classmethod
    def from_node(cls, obj: CoreMenuItem) -> Self:
        return cls(
            id=obj.get_id(),
            name=obj.name.value,
            namespace=obj.namespace.value,
            protected=obj.protected.value,
            description=obj.description.value or "",
            label=obj.label.value or "",
            icon=obj.icon.value or "",
            order_weight=obj.order_weight.value,
            path=obj.path.value or "",
            kind=obj.kind.value or "",
            section=obj.section.value,
            permissions=obj.required_permissions.value or [],
        )

    async def to_node(self, db: InfrahubDatabase, parent: CoreMenuItem | None = None) -> CoreMenuItem:
        obj = await Node.init(db=db, schema=CoreMenuItem)
        await obj.new(
            db=db,
            namespace=self.namespace,
            name=self.name,
            label=self.label,
            kind=self.kind,
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

    @classmethod
    def from_schema(cls, model: NodeSchema | GenericSchema | ProfileSchema | TemplateSchema) -> Self:
        return cls(
            name=model.name,
            namespace=model.namespace,
            label=model.label or model.kind,
            path=f"/objects/{model.kind}",
            icon=model.icon or "",
            kind=model.kind,
        )


class MenuItemDict(MenuItem):
    hidden: bool = False
    children: dict[str, MenuItemDict] = Field(default_factory=dict, description="Child objects")

    def get_all_identifiers(self) -> set[str]:
        identifiers: set[str] = {str(self.identifier)}
        for child in self.children.values():
            identifiers.update(child.get_all_identifiers())
        return identifiers

    def to_list(self) -> MenuItemList:
        data = self.model_dump(exclude={"children", "id"})
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

    def diff_attributes(self, other: Self) -> dict[str, Any]:
        other_attributes = other.model_dump(exclude={"children"})
        self_attributes = self.model_dump(exclude={"children"})
        return {
            key: value
            for key, value in other_attributes.items()
            if value != self_attributes[key] and key not in ["id", "children"]
        }

    @classmethod
    def from_definition(cls, definition: MenuItemDefinition) -> Self:
        menu_item = cls(
            name=definition.name,
            namespace=definition.namespace,
            label=definition.label,
            path=definition.get_path() or "",
            icon=definition.icon,
            kind=definition.kind,
            protected=definition.protected,
            section=definition.section,
            permissions=definition.permissions,
            order_weight=definition.order_weight,
        )

        for child in definition.children:
            menu_item.children[child.full_name] = MenuItemDict.from_definition(definition=child)

        return menu_item


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

    @classmethod
    async def from_node(cls, node: CoreMenuItem) -> Self:
        return cls(
            namespace=node.namespace.value,
            name=node.name.value,
            label=node.label.value or "",
            description=node.description.value or "",
            icon=node.icon.value or "",
            protected=node.protected.value,
            path=node.path.value or "",
            kind=node.kind.value or "",
            section=node.section.value,
            order_weight=node.order_weight.value,
        )

    def get_path(self) -> str | None:
        if self.path:
            return self.path

        if self.kind:
            return f"/objects/{self.kind}"

        return None

    @property
    def full_name(self) -> str:
        return f"{self.namespace}{self.name}"
