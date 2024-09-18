from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Self

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from infrahub.api.dependencies import get_branch_dep, get_db
from infrahub.core import registry
from infrahub.core.branch import Branch  # noqa: TCH001
from infrahub.core.constants import InfrahubKind
from infrahub.core.menu import DEFAULT_MENU
from infrahub.core.protocols import CoreMenuItem
from infrahub.core.schema import NodeSchema
from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.database import InfrahubDatabase

log = get_logger()
router = APIRouter(prefix="/menu")


class InterfaceMenu(BaseModel):
    title: str = Field(..., description="Title of the menu item")
    path: str = Field(default="", description="URL endpoint if applicable")
    icon: str = Field(default="", description="The icon to show for the current view")
    children: list[InterfaceMenu] = Field(default_factory=list, description="Child objects")
    kind: str = Field(default="")

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, InterfaceMenu):
            raise NotImplementedError
        return self.title < other.title

    def list_title(self) -> str:
        return f"All {self.title}(s)"


@dataclass
class Menu:
    data: dict[str, NewInterfaceMenu] = field(default_factory=dict)

    def find_menu_item(self, item_name: str) -> NewInterfaceMenu | None:
        # search at the top level first
        for name, item in self.data.items():
            if name == item_name:
                return item

        # Search amoung the children
        for item in self.data.values():
            if not item.children:
                continue
            found = self.find_menu_item(item_name=item_name)
            if found:
                return found

        return None

    def to_rest(self) -> Menu:
        return Menu(data=self._sort_menu_items(self.data))

    @staticmethod
    def _sort_menu_items(items: dict[str, NewInterfaceMenu]) -> dict[str, NewInterfaceMenu]:
        sorted(items.items(), key=lambda x: (x[1].order_weight, x[0]), reverse=True)
        return items


class NewInterfaceMenu(BaseModel):
    title: str = Field(..., description="Title of the menu item")
    path: str = Field(default="", description="URL endpoint if applicable")
    icon: str = Field(default="", description="The icon to show for the current view")
    children: dict[str, NewInterfaceMenu] = Field(default_factory=dict, description="Child objects")
    kind: str = Field(default="")
    order_weight: int = 5000

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, NewInterfaceMenu):
            raise NotImplementedError
        return self.title < other.title

    @classmethod
    def from_node(cls, obj: CoreMenuItem) -> Self:
        return cls(title=obj.label.value or "", icon=obj.icon.value or "", order_weight=obj.order_weight.value)

    @classmethod
    def from_schema(cls, model: MainSchemaTypes) -> Self:
        return cls(title=model.label or model.kind, path=f"/objects/{model.kind}", icon=model.icon or "")


def add_to_menu(structure: dict[str, list[InterfaceMenu]], menu_item: InterfaceMenu) -> None:
    all_items = InterfaceMenu(title=menu_item.list_title(), path=menu_item.path, icon=menu_item.icon)
    menu_item.path = ""
    menu_item.icon = ""
    for child in structure[menu_item.kind]:
        menu_item.children.append(child)
        if child.kind in structure:
            add_to_menu(structure, child)
    menu_item.children.sort()
    menu_item.children.insert(0, all_items)


def _extract_node_icon(model: MainSchemaTypes) -> str:
    if not model.icon:
        return ""
    return model.icon


@router.get("")
async def get_menu(branch: Branch = Depends(get_branch_dep)) -> list[InterfaceMenu]:
    log.info("menu_request", branch=branch.name)

    full_schema = registry.schema.get_full(branch=branch, duplicate=False)
    objects = InterfaceMenu(title="Objects", children=[])

    structure: dict[str, list[InterfaceMenu]] = {}

    ipam = InterfaceMenu(
        title="IPAM",
        children=[
            InterfaceMenu(
                title="Namespaces",
                path=f"/objects/{InfrahubKind.IPNAMESPACE}",
                icon=_extract_node_icon(full_schema[InfrahubKind.IPNAMESPACE]),
            ),
            InterfaceMenu(
                title="IP Prefixes", path="/ipam/prefixes", icon=_extract_node_icon(full_schema[InfrahubKind.IPPREFIX])
            ),
            InterfaceMenu(
                title="IP Addresses",
                path="/ipam/addresses?ipam-tab=ip-details",
                icon=_extract_node_icon(full_schema[InfrahubKind.IPADDRESS]),
            ),
        ],
    )

    has_ipam = False

    for key in full_schema.keys():
        model = full_schema[key]

        if isinstance(model, NodeSchema) and (
            InfrahubKind.IPADDRESS in model.inherit_from or InfrahubKind.IPPREFIX in model.inherit_from
        ):
            has_ipam = True

        if not model.include_in_menu:
            continue

        menu_name = model.menu_placement or "base"
        if menu_name not in structure:
            structure[menu_name] = []

        structure[menu_name].append(
            InterfaceMenu(title=model.menu_title, path=f"/objects/{model.kind}", icon=model.icon or "", kind=model.kind)
        )

    for menu_item in structure["base"]:
        if menu_item.kind in structure:
            add_to_menu(structure, menu_item)

        objects.children.append(menu_item)

    objects.children.sort()
    groups = InterfaceMenu(
        title="Object Management",
        children=[
            InterfaceMenu(
                title="All Groups",
                path=f"/objects/{InfrahubKind.GENERICGROUP}",
                icon=_extract_node_icon(full_schema[InfrahubKind.GENERICGROUP]),
            ),
            InterfaceMenu(
                title="All Profiles",
                path=f"/objects/{InfrahubKind.PROFILE}",
                icon=_extract_node_icon(full_schema[InfrahubKind.PROFILE]),
            ),
            InterfaceMenu(
                title="Resource Manager",
                path="/resource-manager",
                icon=_extract_node_icon(full_schema[InfrahubKind.RESOURCEPOOL]),
            ),
        ],
    )

    unified_storage = InterfaceMenu(
        title="Unified Storage",
        children=[
            InterfaceMenu(title="Schema", path="/schema", icon="mdi:file-code"),
            InterfaceMenu(
                title="Repository",
                path=f"/objects/{InfrahubKind.GENERICREPOSITORY}",
                icon=_extract_node_icon(full_schema[InfrahubKind.GENERICREPOSITORY]),
            ),
            InterfaceMenu(
                title="GraphQL Query",
                path=f"/objects/{InfrahubKind.GRAPHQLQUERY}",
                icon=_extract_node_icon(full_schema[InfrahubKind.GRAPHQLQUERY]),
            ),
        ],
    )
    change_control = InterfaceMenu(
        title="Change Control",
        children=[
            InterfaceMenu(title="Branches", path="/branches", icon="mdi:layers-triple"),
            InterfaceMenu(
                title="Proposed Changes",
                path="/proposed-changes",
                icon=_extract_node_icon(full_schema[InfrahubKind.PROPOSEDCHANGE]),
            ),
            InterfaceMenu(
                title="Check Definition",
                path=f"/objects/{InfrahubKind.CHECKDEFINITION}",
                icon=_extract_node_icon(full_schema[InfrahubKind.CHECKDEFINITION]),
            ),
            InterfaceMenu(title="Tasks", path="/tasks", icon="mdi:shield-check"),
        ],
    )
    deployment = InterfaceMenu(
        title="Deployment",
        children=[
            InterfaceMenu(
                title="Artifact",
                path=f"/objects/{InfrahubKind.ARTIFACT}",
                icon=_extract_node_icon(full_schema[InfrahubKind.ARTIFACT]),
            ),
            InterfaceMenu(
                title="Artifact Definition",
                path=f"/objects/{InfrahubKind.ARTIFACTDEFINITION}",
                icon=_extract_node_icon(full_schema[InfrahubKind.ARTIFACTDEFINITION]),
            ),
            InterfaceMenu(
                title="Generator Definition",
                path=f"/objects/{InfrahubKind.GENERATORDEFINITION}",
                icon=_extract_node_icon(full_schema[InfrahubKind.GENERATORDEFINITION]),
            ),
            InterfaceMenu(
                title="Generator Instance",
                path=f"/objects/{InfrahubKind.GENERATORINSTANCE}",
                icon=_extract_node_icon(full_schema[InfrahubKind.GENERATORINSTANCE]),
            ),
            InterfaceMenu(
                title="Transformation",
                path=f"/objects/{InfrahubKind.TRANSFORM}",
                icon=_extract_node_icon(full_schema[InfrahubKind.TRANSFORM]),
            ),
        ],
    )

    admin = InterfaceMenu(
        title="Admin",
        children=[
            InterfaceMenu(
                title="Role Management",
                path="/role-management",
                icon=_extract_node_icon(full_schema[InfrahubKind.BASEPERMISSION]),
            ),
            InterfaceMenu(
                title="Credentials",
                path=f"/objects/{InfrahubKind.CREDENTIAL}",
                icon=_extract_node_icon(full_schema[InfrahubKind.CREDENTIAL]),
            ),
            InterfaceMenu(
                title="Webhooks",
                children=[
                    InterfaceMenu(
                        title="Webhook",
                        path=f"/objects/{InfrahubKind.STANDARDWEBHOOK}",
                        icon=_extract_node_icon(full_schema[InfrahubKind.STANDARDWEBHOOK]),
                    ),
                    InterfaceMenu(
                        title="Custom Webhook",
                        path=f"/objects/{InfrahubKind.CUSTOMWEBHOOK}",
                        icon=_extract_node_icon(full_schema[InfrahubKind.CUSTOMWEBHOOK]),
                    ),
                ],
            ),
        ],
    )

    menu_items = [objects]
    if has_ipam:
        menu_items.append(ipam)
    menu_items.extend([groups, unified_storage, change_control, deployment, admin])

    return menu_items


@router.get("/new")
async def get_new_menu(db: InfrahubDatabase = Depends(get_db), branch: Branch = Depends(get_branch_dep)) -> Menu:
    log.info("new_menu_request", branch=branch.name)

    menu_items = await registry.manager.query(db=db, schema=CoreMenuItem, branch=branch, prefetch_relationships=True)
    full_schema = registry.schema.get_full(branch=branch, duplicate=False)

    structure = Menu()

    # Process the parent first
    for item in menu_items:
        parent = await item.parent.get_peer(db=db, peer_type=CoreMenuItem)
        if parent:
            continue
        structure.data[item.name.value] = NewInterfaceMenu.from_node(obj=item)

    # Process the children
    for item in menu_items:
        parent = await item.parent.get_peer(db=db, peer_type=CoreMenuItem)
        if not parent:
            continue

        menu_item = structure.find_menu_item(item_name=parent.name.value)
        if menu_item:
            menu_item.children[item.name.value] = NewInterfaceMenu.from_node(obj=item)
        else:
            log.warning(
                "new_menu_request: unable to find the parent menu item",
                branch=branch.name,
                menu_item=item.name.value,
                parent_item=parent.name.value,
            )

    default_menu = structure.find_menu_item(item_name=DEFAULT_MENU)
    if not default_menu:
        raise ValueError("Unable to locate the default menu item")

    for schema in full_schema.values():
        if schema.include_in_menu is False:
            continue

        menu_item = NewInterfaceMenu.from_schema(model=schema)
        if schema.menu_placement:
            menu_placement = structure.find_menu_item(item_name=schema.menu_placement)

            if menu_placement:
                menu_placement.children[schema.kind] = menu_item
                continue
            log.warning(
                "new_menu_request: unable to find the menu_placement defined in the schema",
                branch=branch.name,
                item=schema.kind,
                menu_placement=schema.menu_placement,
            )

        default_menu.children[schema.kind] = menu_item

    return structure.to_rest()
