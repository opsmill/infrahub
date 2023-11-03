from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from infrahub.api.dependencies import get_branch_dep
from infrahub.core import registry
from infrahub.core.branch import Branch  # noqa: TCH001
from infrahub.core.schema import GroupSchema, NodeSchema
from infrahub.log import get_logger

log = get_logger()
router = APIRouter(prefix="/menu")

EXCLUDED_INHERITED_GENERICS = [
    "CoreCheck",
    "CoreComment",
    "CoreGroup",
    "CoreThread",
    "CoreTransformation",
    "CoreValidator",
    "InfraInterface",
]

EXCLUDED_MODELS = [
    "CoreAccount",
    "CoreArtifact",
    "CoreArtifactDefinition",
    "CoreArtifactTarget",
    "CoreCheck",
    "CoreComment",
    "CoreCheckDefinition",
    "CoreGraphQLQuery",
    "CoreGroup",
    "CoreNode",
    "CoreRepository",
    "CoreProposedChange",
    "CoreRepository",
    "CoreTransformation",
    "CoreThread",
    "CoreValidator",
]
EXCLUDED_NAMESPACES = ["Internal", "Lineage"]


class InterfaceMenu(BaseModel):
    title: str = Field(..., description="Title of the menu item")
    path: str = Field(default="", description="URL endpoint if applicable")
    children: List[InterfaceMenu] = Field(default_factory=list, description="Child objects")

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, InterfaceMenu):
            raise NotImplementedError
        return self.title < other.title


def inherits_from_excluded_generic(model: NodeSchema) -> bool:
    for parent in model.inherit_from:
        if parent in EXCLUDED_INHERITED_GENERICS:
            return True

    return False


@router.get("")
async def get_menu(
    branch: Branch = Depends(get_branch_dep),
) -> List[InterfaceMenu]:
    log.info("menu_request", branch=branch.name)

    full_schema = registry.schema.get_full(branch=branch)

    objects = InterfaceMenu(
        title="Objects",
        children=[],
    )

    groups = InterfaceMenu(
        title="Groups",
    )
    for key in full_schema.keys():
        model = full_schema[key]
        if isinstance(model, GroupSchema) or model.namespace in EXCLUDED_NAMESPACES or model.kind in EXCLUDED_MODELS:
            continue

        if isinstance(model, NodeSchema) and "CoreGroup" in model.inherit_from:
            groups.children.append(InterfaceMenu(title=model.name, path=f"/objects/{model.kind}"))
        if isinstance(model, NodeSchema) and inherits_from_excluded_generic(model):
            continue

        if model.kind == "InfraInterface":
            objects.children.append(
                InterfaceMenu(
                    title="Interfaces",
                    children=[
                        InterfaceMenu(title="Interface L2", path="/objects/InfraInterfaceL2"),
                        InterfaceMenu(title="Interface L3", path="/objects/InfraInterfaceL3"),
                        InterfaceMenu(title="Interface", path="/objects/InfraInterface"),
                    ],
                )
            )
        else:
            objects.children.append(InterfaceMenu(title=model.name, path=f"/objects/{model.kind}"))

    objects.children.sort()
    groups.children.sort()

    unified_storage = InterfaceMenu(
        title="Unified Storage",
        children=[
            InterfaceMenu(title="Schema", path="/schema"),
            InterfaceMenu(title="Repository", path="/objects/CoreCheckDefinition"),
            InterfaceMenu(title="GraphQL Query", path="/objects/CoreGraphQLQuery"),
        ],
    )

    change_control = InterfaceMenu(
        title="Change Control",
        children=[
            InterfaceMenu(title="Branches", path="/branches"),
            InterfaceMenu(title="Proposed Changes", path="/proposed-changes"),
            InterfaceMenu(title="Check Definition", path="/objects/CoreCheckDefinition"),
        ],
    )
    deployment = InterfaceMenu(
        title="Deployment",
        children=[
            InterfaceMenu(title="Artifact", path="/objects/CoreArtifact"),
            InterfaceMenu(title="Artifact Definition", path="/objects/CoreArtifactDefinition"),
            InterfaceMenu(title="Transformation", path="/objects/CoreTransformation"),
        ],
    )
    admin = InterfaceMenu(title="Admin", children=[InterfaceMenu(title="Accounts", path="objects/CoreAccount")])

    return [objects, groups, unified_storage, change_control, deployment, admin]
