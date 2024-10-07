from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import infrahubkind as InfrahubKind
from infrahub.core.schema import SchemaRoot, core_models

from .constants import DEFAULT_MENU, MenuSection
from .models import MenuItem

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes


infrahub_schema = SchemaRoot(**core_models)


def _extract_node_icon(model: MainSchemaTypes) -> str:
    if not model.icon:
        return ""
    return model.icon


default_menu = [
    MenuItem(
        namespace="Builtin",
        name=DEFAULT_MENU,
        label=DEFAULT_MENU.title(),
        protected=True,
        section=MenuSection.OBJECT,
    ),
    MenuItem(
        namespace="Builtin",
        name="ObjectManagement",
        label="Object Management",
        protected=True,
        section=MenuSection.INTERNAL,
        order_weight=1000,
        children=[
            MenuItem(
                namespace="Builtin",
                name="Groups",
                label="Groups",
                kind=InfrahubKind.GENERICGROUP,
                icon=_extract_node_icon(infrahub_schema.get(InfrahubKind.GENERICGROUP)),
                protected=True,
                section=MenuSection.INTERNAL,
                order_weight=1000,
            ),
            MenuItem(
                namespace="Builtin",
                name="Profiles",
                label="Profiles",
                kind=InfrahubKind.PROFILE,
                icon=_extract_node_icon(infrahub_schema.get(InfrahubKind.PROFILE)),
                protected=True,
                section=MenuSection.INTERNAL,
                order_weight=2000,
            ),
            MenuItem(
                namespace="Builtin",
                name="ResourceManager",
                label="Resource Manager",
                path="/resource-manager",
                icon=_extract_node_icon(infrahub_schema.get(InfrahubKind.RESOURCEPOOL)),
                protected=True,
                section=MenuSection.INTERNAL,
                order_weight=3000,
            ),
        ],
    ),
    MenuItem(
        namespace="Builtin",
        name="ChangeControl",
        label="Change Control",
        protected=True,
        section=MenuSection.INTERNAL,
        order_weight=2000,
        children=[
            MenuItem(
                namespace="Builtin",
                name="Branches",
                label="Branches",
                path="/branche",
                icon="mdi:layers-triple",
                protected=True,
                section=MenuSection.INTERNAL,
                order_weight=1000,
            ),
            MenuItem(
                namespace="Builtin",
                name="ProposedChanges",
                label="Proposed Changes",
                path="/proposed-changes",
                icon=_extract_node_icon(infrahub_schema.get(InfrahubKind.PROPOSEDCHANGE)),
                protected=True,
                section=MenuSection.INTERNAL,
                order_weight=2000,
            ),
            MenuItem(
                namespace="Builtin",
                name="CheckDefinition",
                label="Check Definition",
                kind=InfrahubKind.CHECKDEFINITION,
                icon=_extract_node_icon(infrahub_schema.get(InfrahubKind.CHECKDEFINITION)),
                protected=True,
                section=MenuSection.INTERNAL,
                order_weight=3000,
            ),
            MenuItem(
                namespace="Builtin",
                name="Tasks",
                label="Tasks",
                path="/tasks",
                icon="mdi:shield-check",
                protected=True,
                section=MenuSection.INTERNAL,
                order_weight=3000,
            ),
        ],
    ),
    MenuItem(
        namespace="Builtin",
        name="UnifiedStorage",
        label="Unified Storage",
        protected=True,
        section=MenuSection.INTERNAL,
        order_weight=3000,
        children=[
            MenuItem(
                namespace="Builtin",
                name="Schema",
                label="Schema",
                path="/schema",
                icon="mdi:file-code",
                protected=True,
                section=MenuSection.INTERNAL,
                order_weight=1000,
            ),
            MenuItem(
                namespace="Builtin",
                name="Repository",
                label="Repository",
                kind=InfrahubKind.GENERICREPOSITORY,
                icon=_extract_node_icon(infrahub_schema.get(InfrahubKind.GENERICREPOSITORY)),
                protected=True,
                section=MenuSection.INTERNAL,
                order_weight=2000,
            ),
            MenuItem(
                namespace="Builtin",
                name="GraphqlQuery",
                label="GraphQL Query",
                kind=InfrahubKind.GRAPHQLQUERY,
                icon=_extract_node_icon(infrahub_schema.get(InfrahubKind.GRAPHQLQUERY)),
                protected=True,
                section=MenuSection.INTERNAL,
                order_weight=3000,
            ),
        ],
    ),
    MenuItem(
        namespace="Builtin",
        name="Admin",
        label="Admin",
        protected=True,
        section=MenuSection.INTERNAL,
        order_weight=3000,
        children=[
            MenuItem(
                namespace="Builtin",
                name="RoleManagement",
                label="Role Management",
                path="/role-management",
                icon=_extract_node_icon(infrahub_schema.get(InfrahubKind.BASEPERMISSION)),
                protected=True,
                section=MenuSection.INTERNAL,
                order_weight=1000,
            ),
            MenuItem(
                namespace="Builtin",
                name="Credentials",
                label="Credentials",
                kind=InfrahubKind.CREDENTIAL,
                icon=_extract_node_icon(infrahub_schema.get(InfrahubKind.CREDENTIAL)),
                protected=True,
                section=MenuSection.INTERNAL,
                order_weight=2000,
            ),
            MenuItem(
                namespace="Builtin",
                name="Webhooks",
                label="Webhooks",
                icon=_extract_node_icon(infrahub_schema.get(InfrahubKind.CUSTOMWEBHOOK)),
                protected=True,
                section=MenuSection.INTERNAL,
                order_weight=3000,
                children=[
                    MenuItem(
                        namespace="Builtin",
                        name="WebhookStandard",
                        label="Webhook",
                        kind=InfrahubKind.STANDARDWEBHOOK,
                        icon=_extract_node_icon(infrahub_schema.get(InfrahubKind.STANDARDWEBHOOK)),
                        protected=True,
                        section=MenuSection.INTERNAL,
                        order_weight=1000,
                    ),
                    MenuItem(
                        namespace="Builtin",
                        name="WebhookCustom",
                        label="Custom Webhook",
                        kind=InfrahubKind.CUSTOMWEBHOOK,
                        icon=_extract_node_icon(infrahub_schema.get(InfrahubKind.CUSTOMWEBHOOK)),
                        protected=True,
                        section=MenuSection.INTERNAL,
                        order_weight=2000,
                    ),
                ],
            ),
        ],
    ),
]


#     deployment = InterfaceMenu(
#         title="Deployment",
#         children=[
#             InterfaceMenu(
#                 title="Artifact",
#                 kind=InfrahubKind.ARTIFACT}",
#                 icon=_extract_node_icon(full_schema[InfrahubKind.ARTIFACT]),
#             ),
#             InterfaceMenu(
#                 title="Artifact Definition",
#                 kind=InfrahubKind.ARTIFACTDEFINITION}",
#                 icon=_extract_node_icon(full_schema[InfrahubKind.ARTIFACTDEFINITION]),
#             ),
#             InterfaceMenu(
#                 title="Generator Definition",
#                 kind=InfrahubKind.GENERATORDEFINITION}",
#                 icon=_extract_node_icon(full_schema[InfrahubKind.GENERATORDEFINITION]),
#             ),
#             InterfaceMenu(
#                 title="Generator Instance",
#                 kind=InfrahubKind.GENERATORINSTANCE}",
#                 icon=_extract_node_icon(full_schema[InfrahubKind.GENERATORINSTANCE]),
#             ),
#             InterfaceMenu(
#                 title="Transformation",
#                 kind=InfrahubKind.TRANSFORM}",
#                 icon=_extract_node_icon(full_schema[InfrahubKind.TRANSFORM]),
#             ),
#         ],
#     )
