from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import infrahubkind as InfrahubKind
from infrahub.core.schema import SchemaRoot, core_models

from .constants import DEFAULT_MENU, MenuSection
from .models import MenuItemDefinition

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes


infrahub_schema = SchemaRoot(**core_models)


def _extract_node_icon(model: MainSchemaTypes) -> str:
    if not model.icon:
        return ""
    return model.icon


default_menu = [
    MenuItemDefinition(
        namespace="Builtin",
        name=DEFAULT_MENU,
        label=DEFAULT_MENU.title(),
        protected=True,
        icon="mdi:cube-outline",
        section=MenuSection.OBJECT,
        order_weight=10000,
    ),
    MenuItemDefinition(
        namespace="Builtin",
        name="IPAM",
        label="IPAM",
        protected=True,
        section=MenuSection.OBJECT,
        icon="mdi:ip-network",
        order_weight=9500,
        children=[
            MenuItemDefinition(
                namespace="Builtin",
                name="IPPrefix",
                label="IP Prefixes",
                kind=InfrahubKind.IPPREFIX,
                path="/ipam/prefixes",
                icon=_extract_node_icon(infrahub_schema.get(InfrahubKind.IPPREFIX)),
                protected=True,
                section=MenuSection.INTERNAL,
                order_weight=1000,
            ),
            MenuItemDefinition(
                namespace="Builtin",
                name="IPAddress",
                label="IP Addresses",
                kind=InfrahubKind.IPPREFIX,
                path="/ipam/addresses?ipam-tab=ip-details",
                icon=_extract_node_icon(infrahub_schema.get(InfrahubKind.IPADDRESS)),
                protected=True,
                section=MenuSection.INTERNAL,
                order_weight=2000,
            ),
            MenuItemDefinition(
                namespace="Builtin",
                name="Namespaces",
                label="Namespaces",
                kind=InfrahubKind.IPNAMESPACE,
                icon=_extract_node_icon(infrahub_schema.get(InfrahubKind.IPNAMESPACE)),
                protected=True,
                section=MenuSection.INTERNAL,
                order_weight=3000,
            ),
        ],
    ),
    MenuItemDefinition(
        namespace="Builtin",
        name="ProposedChanges",
        label="Proposed Changes",
        path="/proposed-changes",
        icon=_extract_node_icon(infrahub_schema.get(InfrahubKind.PROPOSEDCHANGE)),
        protected=True,
        section=MenuSection.INTERNAL,
        order_weight=1000,
    ),
    MenuItemDefinition(
        namespace="Builtin",
        name="ObjectManagement",
        label="Object Management",
        icon="mdi:cube-outline",
        protected=True,
        section=MenuSection.INTERNAL,
        order_weight=1500,
        children=[
            MenuItemDefinition(
                namespace="Builtin",
                name="Groups",
                label="Groups",
                kind=InfrahubKind.GENERICGROUP,
                icon=_extract_node_icon(infrahub_schema.get(InfrahubKind.GENERICGROUP)),
                protected=True,
                section=MenuSection.INTERNAL,
                order_weight=1000,
            ),
            MenuItemDefinition(
                namespace="Builtin",
                name="Profiles",
                label="Profiles",
                kind=InfrahubKind.PROFILE,
                icon=_extract_node_icon(infrahub_schema.get(InfrahubKind.PROFILE)),
                protected=True,
                section=MenuSection.INTERNAL,
                order_weight=2000,
            ),
            MenuItemDefinition(
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
    MenuItemDefinition(
        namespace="Builtin",
        name="ChangeControl",
        label="Change Control",
        icon="mdi:source-branch",
        protected=True,
        section=MenuSection.INTERNAL,
        order_weight=2000,
        children=[
            MenuItemDefinition(
                namespace="Builtin",
                name="Branches",
                label="Branches",
                path="/branches",
                icon="mdi:layers-triple",
                protected=True,
                section=MenuSection.INTERNAL,
                order_weight=1000,
            ),
            MenuItemDefinition(
                namespace="Builtin",
                name="CheckDefinition",
                label="Check Definition",
                kind=InfrahubKind.CHECKDEFINITION,
                icon=_extract_node_icon(infrahub_schema.get(InfrahubKind.CHECKDEFINITION)),
                protected=True,
                section=MenuSection.INTERNAL,
                order_weight=3000,
            ),
            MenuItemDefinition(
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
    MenuItemDefinition(
        namespace="Builtin",
        name="Deployment",
        label="Deployment",
        icon="mdi:rocket-launch",
        protected=True,
        section=MenuSection.INTERNAL,
        order_weight=2500,
        children=[
            MenuItemDefinition(
                namespace="Builtin",
                name="ArtifactMenu",
                label="Artifact",
                protected=True,
                section=MenuSection.INTERNAL,
                order_weight=1000,
                children=[
                    MenuItemDefinition(
                        namespace="Builtin",
                        name="Artifact",
                        label="Artifact",
                        kind=InfrahubKind.ARTIFACT,
                        icon=_extract_node_icon(infrahub_schema.get(InfrahubKind.ARTIFACT)),
                        protected=True,
                        section=MenuSection.INTERNAL,
                        order_weight=1000,
                    ),
                    MenuItemDefinition(
                        namespace="Builtin",
                        name="ArtifactDefinition",
                        label="Artifact Definition",
                        kind=InfrahubKind.ARTIFACTDEFINITION,
                        icon=_extract_node_icon(infrahub_schema.get(InfrahubKind.ARTIFACTDEFINITION)),
                        protected=True,
                        section=MenuSection.INTERNAL,
                        order_weight=1000,
                    ),
                ],
            ),
            MenuItemDefinition(
                namespace="Builtin",
                name="GeneratorMenu",
                label="Generator",
                protected=True,
                section=MenuSection.INTERNAL,
                order_weight=1000,
                children=[
                    MenuItemDefinition(
                        namespace="Builtin",
                        name="GeneratorInstance",
                        label="Generator Instance",
                        kind=InfrahubKind.GENERATORINSTANCE,
                        icon=_extract_node_icon(infrahub_schema.get(InfrahubKind.GENERATORINSTANCE)),
                        protected=True,
                        section=MenuSection.INTERNAL,
                        order_weight=1000,
                    ),
                    MenuItemDefinition(
                        namespace="Builtin",
                        name="GeneratorDefinition",
                        label="Generator Definition",
                        kind=InfrahubKind.GENERATORDEFINITION,
                        icon=_extract_node_icon(infrahub_schema.get(InfrahubKind.GENERATORDEFINITION)),
                        protected=True,
                        section=MenuSection.INTERNAL,
                        order_weight=2000,
                    ),
                ],
            ),
            MenuItemDefinition(
                namespace="Builtin",
                name="Transformation",
                label="Transformation",
                kind=InfrahubKind.TRANSFORM,
                icon=_extract_node_icon(infrahub_schema.get(InfrahubKind.TRANSFORM)),
                protected=True,
                section=MenuSection.INTERNAL,
                order_weight=3000,
            ),
        ],
    ),
    MenuItemDefinition(
        namespace="Builtin",
        name="UnifiedStorage",
        label="Unified Storage",
        icon="mdi:nas",
        protected=True,
        section=MenuSection.INTERNAL,
        order_weight=3000,
        children=[
            MenuItemDefinition(
                namespace="Builtin",
                name="Schema",
                label="Schema",
                path="/schema",
                icon="mdi:file-code",
                protected=True,
                section=MenuSection.INTERNAL,
                order_weight=1000,
            ),
            MenuItemDefinition(
                namespace="Builtin",
                name="Git Repository",
                label="Repository",
                kind=InfrahubKind.GENERICREPOSITORY,
                icon=_extract_node_icon(infrahub_schema.get(InfrahubKind.GENERICREPOSITORY)),
                protected=True,
                section=MenuSection.INTERNAL,
                order_weight=2000,
            ),
            MenuItemDefinition(
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
    MenuItemDefinition(
        namespace="Builtin",
        name="Admin",
        label="Admin",
        icon="mdi:settings-outline",
        protected=True,
        section=MenuSection.INTERNAL,
        order_weight=10000,
        children=[
            MenuItemDefinition(
                namespace="Builtin",
                name="RoleManagement",
                label="Role Management",
                path="/role-management",
                icon=_extract_node_icon(infrahub_schema.get(InfrahubKind.BASEPERMISSION)),
                protected=True,
                section=MenuSection.INTERNAL,
                order_weight=1000,
            ),
            MenuItemDefinition(
                namespace="Builtin",
                name="Credentials",
                label="Credentials",
                kind=InfrahubKind.CREDENTIAL,
                icon=_extract_node_icon(infrahub_schema.get(InfrahubKind.CREDENTIAL)),
                protected=True,
                section=MenuSection.INTERNAL,
                order_weight=2000,
            ),
            MenuItemDefinition(
                namespace="Builtin",
                name="Webhooks",
                label="Webhooks",
                icon=_extract_node_icon(infrahub_schema.get(InfrahubKind.CUSTOMWEBHOOK)),
                protected=True,
                section=MenuSection.INTERNAL,
                order_weight=3000,
                children=[
                    MenuItemDefinition(
                        namespace="Builtin",
                        name="WebhookStandard",
                        label="Webhook",
                        kind=InfrahubKind.STANDARDWEBHOOK,
                        icon=_extract_node_icon(infrahub_schema.get(InfrahubKind.STANDARDWEBHOOK)),
                        protected=True,
                        section=MenuSection.INTERNAL,
                        order_weight=1000,
                    ),
                    MenuItemDefinition(
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
