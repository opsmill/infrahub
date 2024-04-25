from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from infrahub.api.dependencies import get_branch_dep
from infrahub.core import registry
from infrahub.core.branch import Branch  # noqa: TCH001
from infrahub.core.constants import InfrahubKind
from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes

log = get_logger()
router = APIRouter(prefix="/menu")


class InterfaceMenu(BaseModel):
    title: str = Field(..., description="Title of the menu item")
    path: str = Field(default="", description="URL endpoint if applicable")
    icon: str = Field(default="", description="The icon to show for the current view")
    children: List[InterfaceMenu] = Field(default_factory=list, description="Child objects")
    kind: str = Field(default="")

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, InterfaceMenu):
            raise NotImplementedError
        return self.title < other.title

    def list_title(self) -> str:
        return f"All {self.title}(s)"


def add_to_menu(structure: Dict[str, List[InterfaceMenu]], menu_item: InterfaceMenu) -> None:
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
async def get_menu(
    branch: Branch = Depends(get_branch_dep),
) -> List[InterfaceMenu]:
    log.info("menu_request", branch=branch.name)

    full_schema = registry.schema.get_full(branch=branch, duplicate=False)
    objects = InterfaceMenu(
        title="Objects",
        children=[],
    )

    structure: Dict[str, List[InterfaceMenu]] = {}

    ipam = InterfaceMenu(
        title="IPAM",
        children=[
            InterfaceMenu(
                title="Namespaces",
                path=f"/objects/{InfrahubKind.IPNAMESPACE}",
                icon=_extract_node_icon(full_schema[InfrahubKind.IPNAMESPACE]),
            ),
            InterfaceMenu(
                title="Prefixes", path="/ipam/prefixes", icon=_extract_node_icon(full_schema[InfrahubKind.IPPREFIX])
            ),
            InterfaceMenu(
                title="IP Addresses",
                path="/ipam/addresses?ipam-tab=ip-details",
                icon=_extract_node_icon(full_schema[InfrahubKind.IPADDRESS]),
            ),
        ],
    )

    for key in full_schema.keys():
        model = full_schema[key]

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
        title="Groups & Profiles",
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
        ],
    )
    unified_storage = InterfaceMenu(
        title="Unified Storage",
        children=[
            InterfaceMenu(title="Schema", path="/schema", icon="mdi:file-code"),
            InterfaceMenu(
                title="Repository",
                path=f"/objects/{InfrahubKind.REPOSITORY}",
                icon=_extract_node_icon(full_schema[InfrahubKind.REPOSITORY]),
            ),
            InterfaceMenu(
                title="Read-only Repository",
                path=f"/objects/{InfrahubKind.READONLYREPOSITORY}",
                icon="mdi:source-repository",
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
                title="Accounts",
                path=f"/objects/{InfrahubKind.ACCOUNT}",
                icon=_extract_node_icon(full_schema[InfrahubKind.ACCOUNT]),
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

    return [objects, ipam, groups, unified_storage, change_control, deployment, admin]
