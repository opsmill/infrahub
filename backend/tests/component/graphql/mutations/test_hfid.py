from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from infrahub.core.account import GlobalPermission, ObjectPermission
from infrahub.core.branch.models import Branch
from infrahub.core.constants import GlobalPermissions, PermissionAction, PermissionDecision, RelationshipCardinality
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.services import InfrahubServices
from tests.adapters.event import MemoryInfrahubEvent
from tests.helpers.graphql import graphql
from tests.helpers.permissions import define_permissions
from tests.helpers.schema import COLOR, TSHIRT, WIDGET

if TYPE_CHECKING:
    from infrahub.auth import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


async def test_update_hfid_missing_kind(
    db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch
) -> None:
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=UPDATE_HFID,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": str(uuid4()), "kind": "InvalidNodeKind", "value": ["very-new-label"]},
    )
    assert result.errors
    assert "Unable to find the schema 'InvalidNodeKind' in the registry" in str(result.errors)


async def test_update_hfid_not_defined(
    db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch
) -> None:
    schema_root = SchemaRoot(nodes=[WIDGET])
    registry.schema.register_schema(schema=schema_root, branch=default_branch.name)
    default_branch.update_schema_hash()

    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=UPDATE_HFID,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": str(uuid4()), "kind": WIDGET.kind, "value": ["very-new-label"]},
    )
    assert result.errors
    assert f"{WIDGET.kind}.human_friendly_id has not been defined for this kind" in str(result.errors)


async def test_update_hfid_update(
    db: InfrahubDatabase,
    register_core_models_schema: None,
    default_branch: Branch,
    default_permission_backend: None,
    session_first_account: AccountSession,
    first_account: Node,
) -> None:
    schema_root = SchemaRoot(nodes=[COLOR, TSHIRT])
    registry.schema.register_schema(schema=schema_root, branch=default_branch.name)

    await define_permissions(
        account=first_account,
        db=db,
        global_permissions=[
            GlobalPermission(
                action=GlobalPermissions.UPDATE_OBJECT_HFID_DISPLAY_LABEL.value,
                decision=PermissionDecision.ALLOW_ALL.value,
            )
        ],
        object_permissions=[
            ObjectPermission(
                namespace=TSHIRT.namespace,
                name=TSHIRT.name,
                action=PermissionAction.UPDATE.value,
                decision=PermissionDecision.ALLOW_ALL.value,
            ),
        ],
    )

    c1 = await Node.init(db=db, schema=COLOR.kind)
    await c1.new(db=db, name="Blue", description="A vibrant blue")
    await c1.save(db=db)

    t1 = await Node.init(db=db, schema=TSHIRT.kind)
    await t1.new(db=db, name="Ocean", color=c1)
    await t1.save(db=db)
    default_branch.update_schema_hash()
    event = MemoryInfrahubEvent()
    service = await InfrahubServices.new(event=event)
    gql_params = await prepare_graphql_params(
        db=db, branch=default_branch, account_session=session_first_account, service=service
    )

    missing_node = await graphql(
        schema=gql_params.schema,
        source=UPDATE_HFID,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": str(uuid4()), "kind": TSHIRT.kind, "value": ["very-new-label"]},
    )
    assert missing_node.errors
    assert "The targeted node was not found in the database" in str(missing_node.errors)

    before_change = await graphql(
        schema=gql_params.schema,
        source=QUERY_TSHIRT,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": t1.get_id()},
    )
    assert not before_change.errors
    assert before_change.data
    assert before_change.data["TestingTShirt"]["count"] == 1
    assert before_change.data["TestingTShirt"]["edges"][0]["node"]["hfid"] == ["Ocean"]

    existing_node = await graphql(
        schema=gql_params.schema,
        source=UPDATE_HFID,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": t1.get_id(), "kind": TSHIRT.kind, "value": ["Space"]},
    )
    assert not existing_node.errors
    assert existing_node.data

    gql_params = await prepare_graphql_params(
        db=db, branch=default_branch, account_session=session_first_account, service=service
    )
    after_change = await graphql(
        schema=gql_params.schema,
        source=QUERY_TSHIRT,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": t1.get_id()},
    )
    assert not after_change.errors
    assert after_change.data
    assert after_change.data["TestingTShirt"]["count"] == 1
    assert after_change.data["TestingTShirt"]["edges"][0]["node"]["hfid"] == ["Space"]


UPDATE_HFID = """
mutation UpdateHFID(
  $id: String!
  $kind: String!
  $value: [String!]!
) {
  InfrahubUpdateHFID(data: {id: $id, kind: $kind, value: $value}) {
    ok
  }
}
"""


QUERY_TSHIRT = """
query MyTShirt($id: ID!) {
    TestingTShirt(ids: [$id]) {
        count
        edges {
            node {
                display_label
                hfid
            }
        }
    }
}
"""


async def test_create_nodes_with_relational_hfids(
    db: InfrahubDatabase,
    node_group_schema: None,
    default_branch: Branch,
) -> None:
    """Validate that the correct display label is assigned when creating nodes."""
    schema_root = SchemaRoot(
        nodes=[
            NodeSchema(
                name="Widget",
                namespace="Test",
                attributes=[AttributeSchema(name="name", kind="Text"), AttributeSchema(name="status", kind="Text")],
                relationships=[
                    RelationshipSchema(
                        name="container", peer="TestContainer", cardinality=RelationshipCardinality.ONE, optional=False
                    )
                ],
                display_labels=["name__value", "status"],
                display_label="{{ name__value|upper }}: {{ status__value|lower }} - {{ container__storage_name__value }}",
                human_friendly_id=["name__value", "status__value", "container__storage_name__value"],
            ),
            NodeSchema(
                name="Container",
                namespace="Test",
                default_filter="storage_name__value",
                attributes=[
                    AttributeSchema(name="storage_name", kind="Text", unique=True, optional=False),
                    AttributeSchema(name="status", kind="Text"),
                ],
                display_label="storage_name__value",
            ),
            NodeSchema(
                name="Owner",
                namespace="Test",
                attributes=[
                    AttributeSchema(name="family_name", kind="Text", unique=True, optional=False),
                    AttributeSchema(name="description", kind="Text", optional=True),
                ],
                display_label="family_name__value",
            ),
        ]
    )

    registry.schema.register_schema(schema=schema_root, branch=default_branch.name)

    async with db.start_transaction() as dbt:
        container1 = await Node.init(db=dbt, schema="TestContainer")
        await container1.new(db=dbt, storage_name="WarehouseA", status="Active")
        await container1.save(db=dbt)

    event = MemoryInfrahubEvent()
    service = await InfrahubServices.new(event=event)

    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch, service=service)

    create_widget = """
    mutation TestWidgetCreate($name: String!, $container_id: String, $container_hfid: [String!]) {
        TestWidgetCreate(data:
        {
            name: { value: $name},
            status: { value: "NEW"},
            container: {id: $container_id, hfid: $container_hfid}
        }) {
            ok
            object {
                id
                hfid
            }
        }
    }
    """

    widget1 = await graphql(
        schema=gql_params.schema,
        source=create_widget,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"name": "Trinket1", "container_id": "WarehouseA"},
    )
    assert widget1.errors is None
    assert widget1.data
    assert widget1.data["TestWidgetCreate"]["ok"] is True
    assert widget1.data["TestWidgetCreate"]["object"]["hfid"] == ["Trinket1", "NEW", "WarehouseA"]

    widget2 = await graphql(
        schema=gql_params.schema,
        source=create_widget,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"name": "Trinket2", "container_hfid": ["WarehouseA"]},
    )
    assert widget2.errors is None
    assert widget2.data
    assert widget2.data["TestWidgetCreate"]["ok"] is True
    assert widget2.data["TestWidgetCreate"]["object"]["hfid"] == ["Trinket2", "NEW", "WarehouseA"]
