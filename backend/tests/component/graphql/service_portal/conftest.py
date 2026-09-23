from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.core.constants import InfrahubKind, PermissionAction, RelationshipCardinality, RelationshipKind
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.dropdown import DropdownChoice
from infrahub.permissions.constants import PermissionDecisionFlag
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

CIRCUIT_KIND = "TestingCircuit"
PROVIDER_KIND = "TestingProvider"
CIRCUIT_FIELDS = ["name", "speed", "vlan", "provider", "description"]

PROVIDER = NodeSchema(
    name="Provider",
    namespace="Testing",
    default_filter="name__value",
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
)

CIRCUIT = NodeSchema(
    name="Circuit",
    namespace="Testing",
    default_filter="name__value",
    generate_template=True,
    attributes=[
        AttributeSchema(name="name", kind="Text", regex="^[a-z0-9-]+$"),
        AttributeSchema(
            name="speed", kind="Dropdown", choices=[DropdownChoice(name="small"), DropdownChoice(name="large")]
        ),
        AttributeSchema(name="vlan", kind="Number", optional=True),
        AttributeSchema(name="description", kind="Text", optional=True),
    ],
    relationships=[
        RelationshipSchema(
            name="provider",
            peer=PROVIDER_KIND,
            kind=RelationshipKind.ATTRIBUTE,
            optional=False,
            cardinality=RelationshipCardinality.ONE,
        ),
    ],
)


@dataclass
class ServicePortalData:
    provider: Node
    tag: Node
    entry: Node
    """Review-mode entry for circuits, fields in form order."""
    direct_entry: Node
    requester: Node
    """Account allowed to create circuits on branches other than the default one only."""


@pytest.fixture
async def circuit_schema(db: InfrahubDatabase, register_core_models_schema: SchemaBranch) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[PROVIDER, CIRCUIT]))


async def create_node(db: InfrahubDatabase, kind: str, branch: Branch | None = None, **data: Any) -> Node:
    node = await Node.init(db=db, schema=kind, branch=branch)
    await node.new(db=db, **data)
    await node.save(db=db)
    return node


async def create_account(db: InfrahubDatabase, name: str, create_decision: PermissionDecisionFlag | None) -> Node:
    """Create an account that may view anything and create circuits with the given decision."""
    permissions = [
        await create_node(
            db=db,
            kind=InfrahubKind.OBJECTPERMISSION,
            namespace="*",
            name="*",
            action=PermissionAction.VIEW.value,
            decision=PermissionDecisionFlag.ALLOW_ALL.value,
        )
    ]
    if create_decision is not None:
        permissions.append(
            await create_node(
                db=db,
                kind=InfrahubKind.OBJECTPERMISSION,
                namespace="Testing",
                name="Circuit",
                action=PermissionAction.CREATE.value,
                decision=create_decision.value,
            )
        )
    role = await create_node(db=db, kind=InfrahubKind.ACCOUNTROLE, name=f"{name}-role", permissions=permissions)
    account = await create_node(db=db, kind=InfrahubKind.ACCOUNT, name=name, password="Password123")
    await create_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name=f"{name}-group", roles=[role], members=[account])
    return account


def session_for(account: Node) -> AccountSession:
    return AccountSession(authenticated=True, account_id=account.id, auth_type=AuthType.API)


@pytest.fixture
async def service_portal_data(
    db: InfrahubDatabase, default_branch: Branch, circuit_schema: None, default_permission_backend: None
) -> ServicePortalData:
    provider = await create_node(db=db, kind=PROVIDER_KIND, name="acme")
    tag = await create_node(db=db, kind=InfrahubKind.TAG, name="network")
    return ServicePortalData(
        provider=provider,
        tag=tag,
        entry=await create_node(
            db=db,
            kind=InfrahubKind.SERVICECATALOGENTRY,
            name="Circuit",
            description="A circuit",
            icon="mdi:cable-data",
            target_kind=CIRCUIT_KIND,
            generators=["zeta", "alpha"],
            fields=CIRCUIT_FIELDS,
            tags=[tag],
        ),
        direct_entry=await create_node(
            db=db,
            kind=InfrahubKind.SERVICECATALOGENTRY,
            name="Direct Circuit",
            target_kind=CIRCUIT_KIND,
            mode="direct",
            fields=CIRCUIT_FIELDS,
        ),
        requester=await create_account(db=db, name="requester", create_decision=PermissionDecisionFlag.ALLOW_OTHER),
    )


@dataclass
class TemplateEntry:
    entry: Node
    """Review-mode entry for circuits whose template sets the speed and the provider."""
    template: Node


@pytest.fixture
async def template_entry(db: InfrahubDatabase, service_portal_data: ServicePortalData) -> TemplateEntry:
    template = await create_node(
        db=db,
        kind=f"Template{CIRCUIT_KIND}",
        template_name="gold",
        speed="large",
        provider=service_portal_data.provider,
    )
    entry = await create_node(
        db=db,
        kind=InfrahubKind.SERVICECATALOGENTRY,
        name="Gold Circuit",
        target_kind=CIRCUIT_KIND,
        fields=CIRCUIT_FIELDS,
        template=template,
    )
    return TemplateEntry(entry=entry, template=template)
