import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.menu.constants import DEFAULT_MENU
from infrahub.menu.models import MenuItemDefinition, MenuSection


@pytest.fixture
async def menu_fixture_01_data() -> list[MenuItemDefinition]:
    return [
        MenuItemDefinition(
            namespace="Userdefined",
            name="Test",
            label="Test",
            protected=False,
            icon="mdi:cube-outline",
            section=MenuSection.OBJECT,
            order_weight=12000,
        ),
        MenuItemDefinition(
            namespace="Builtin",
            name=DEFAULT_MENU,
            label=DEFAULT_MENU.title(),
            protected=True,
            icon="mdi:cube-outline",
            section=MenuSection.OBJECT,
            order_weight=10000,
            children=[
                MenuItemDefinition(
                    namespace="Builtin",
                    name="Tag",
                    label="Tags",
                    kind=InfrahubKind.TAG,
                    protected=True,
                    section=MenuSection.OBJECT,
                    order_weight=10000,
                )
            ],
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
                    path="/ipam",
                    protected=True,
                    section=MenuSection.INTERNAL,
                    order_weight=1000,
                ),
                MenuItemDefinition(
                    namespace="Builtin",
                    name="IPAddress",
                    label="IP Addresses",
                    kind=InfrahubKind.IPPREFIX,
                    path="/ipam/ip_addresses",
                    protected=True,
                    section=MenuSection.INTERNAL,
                    order_weight=2000,
                ),
            ],
        ),
        MenuItemDefinition(
            namespace="Builtin",
            name="ProposedChanges",
            label="Proposed Changes",
            path="/proposed-changes",
            protected=True,
            section=MenuSection.INTERNAL,
            order_weight=1000,
        ),
        MenuItemDefinition(
            namespace="Builtin",
            name="Deployment",
            label="Deployment",
            icon="mdi:rocket-launch",
            protected=True,
            section=MenuSection.INTERNAL,
            order_weight=3000,
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
                            protected=True,
                            section=MenuSection.INTERNAL,
                            order_weight=1000,
                        ),
                    ],
                ),
            ],
        ),
    ]
