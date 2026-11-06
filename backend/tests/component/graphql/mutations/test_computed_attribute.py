from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.account import ObjectPermission
from infrahub.core.constants import ComputedAttributeKind, PermissionAction, PermissionDecision
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.computed_attribute import ComputedAttribute
from infrahub.events.constants import NODE_ORIGIN_LABEL, NodeMutationOrigin
from infrahub.events.node_action import NodeUpdatedEvent
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.services import InfrahubServices
from tests.adapters.event import MemoryInfrahubEvent
from tests.helpers.graphql import graphql
from tests.helpers.permissions import define_permissions
from tests.helpers.schema import COLOR, TSHIRT, load_schema

if TYPE_CHECKING:
    from infrahub.auth.session import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


UPDATE_COMPUTED_ATTRIBUTE_MUTATION = """
mutation UpdateComputed($id: String!, $kind: String!, $attribute: String!, $value: String!) {
    InfrahubUpdateComputedAttribute(data: {id: $id, kind: $kind, attribute: $attribute, value: $value}) {
        ok
    }
}
"""


async def test_update_computed_attribute_sends_node_updated_event(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    default_permission_backend: None,
    session_first_account: AccountSession,
    first_account: Node,
) -> None:
    """UpdateComputedAttribute emits a NodeUpdatedEvent with the correct node, fields and display_label."""
    await load_schema(db, schema=SchemaRoot(nodes=[COLOR, TSHIRT]))

    await define_permissions(
        account=first_account,
        db=db,
        object_permissions=[
            ObjectPermission(
                namespace=TSHIRT.namespace,
                name=TSHIRT.name,
                action=PermissionAction.UPDATE.value,
                decision=PermissionDecision.ALLOW_ALL.value,
            ),
        ],
    )

    color = await Node.init(db=db, schema=COLOR.kind, branch=default_branch)
    await color.new(db=db, name="Blue", description="A vibrant blue")
    await color.save(db=db)

    tshirt = await Node.init(db=db, schema=TSHIRT.kind, branch=default_branch)
    await tshirt.new(db=db, name="Ocean", color=color)
    await tshirt.save(db=db)

    assert tshirt.description.value == "A Blue Ocean t-shirt. A vibrant blue"

    memory_event = MemoryInfrahubEvent()
    service = await InfrahubServices.new(event=memory_event)
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db, branch=default_branch, service=service, account_session=session_first_account
    )

    result = await graphql(
        schema=gql_params.schema,
        source=UPDATE_COMPUTED_ATTRIBUTE_MUTATION,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "id": tshirt.id,
            "kind": TSHIRT.kind,
            "attribute": "description",
            "value": "A Blue Ocean t-shirt. A vibrant blue - updated",
        },
    )

    assert result.errors is None
    assert result.data
    assert result.data["InfrahubUpdateComputedAttribute"]["ok"] is True

    assert len(memory_event.events) == 1
    event = memory_event.events[0]
    assert isinstance(event, NodeUpdatedEvent)
    assert event.node_id == tshirt.id
    assert event.kind == TSHIRT.kind
    assert "description" in event.fields
    # The recompute write must emit live origin; a merge/rebase origin would be suppressed by the
    # coalesced recompute, leaving dependent values stale.
    assert event.get_resource()[NODE_ORIGIN_LABEL] == NodeMutationOrigin.LIVE.value
    # The display label of the node within the event must include the correct label
    # even if the display label contains a related node
    assert event.changelog.display_label == "Ocean Blue"


AUTONOMOUS_SYSTEM = NodeSchema(
    name="AutonomousSystem",
    namespace="Testing",
    display_label="AS{{ asn__value }} - {{ name__value }}",
    human_friendly_id=["name__value"],
    attributes=[
        AttributeSchema(name="asn", kind="Number", unique=True),
        AttributeSchema(
            name="name",
            kind="Text",
            unique=True,
            read_only=True,
            optional=False,
            computed_attribute=ComputedAttribute(
                kind=ComputedAttributeKind.JINJA2, jinja2_template="AS{{ asn__value }}"
            ),
        ),
    ],
)

AUTONOMOUS_SYSTEM_BY_HFID_QUERY = """
query AutonomousSystemByHfid($hfid: [String!]) {
    TestingAutonomousSystem(hfid: $hfid) {
        edges {
            node {
                display_label
                hfid
            }
        }
    }
}
"""


async def test_update_computed_attribute_refreshes_labels_that_read_other_attributes(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    default_permission_backend: None,
    session_first_account: AccountSession,
    first_account: Node,
) -> None:
    """The display label and HFID are recomputed from all the attributes they read, and stored as sent in the event."""
    await load_schema(db, schema=SchemaRoot(nodes=[AUTONOMOUS_SYSTEM]))
    await define_permissions(
        account=first_account,
        db=db,
        object_permissions=[
            ObjectPermission(
                namespace=AUTONOMOUS_SYSTEM.namespace,
                name=AUTONOMOUS_SYSTEM.name,
                action=PermissionAction.UPDATE.value,
                decision=PermissionDecision.ALLOW_ALL.value,
            ),
        ],
    )
    autonomous_system = await Node.init(db=db, schema=AUTONOMOUS_SYSTEM.kind, branch=default_branch)
    await autonomous_system.new(db=db, asn=1299)
    await autonomous_system.save(db=db)

    memory_event = MemoryInfrahubEvent()
    service = await InfrahubServices.new(event=memory_event)
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=db, branch=default_branch, service=service, account_session=session_first_account
    )

    result = await graphql(
        schema=gql_params.schema,
        source=UPDATE_COMPUTED_ATTRIBUTE_MUTATION,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "id": autonomous_system.id,
            "kind": AUTONOMOUS_SYSTEM.kind,
            "attribute": "name",
            "value": "Telia",
        },
    )

    assert result.errors is None
    [event] = memory_event.events
    assert isinstance(event, NodeUpdatedEvent)
    assert event.changelog.display_label == "AS1299 - Telia"

    query_params = await prepare_graphql_params(
        db=db, branch=default_branch, service=service, account_session=session_first_account
    )
    lookup = await graphql(
        schema=query_params.schema,
        source=AUTONOMOUS_SYSTEM_BY_HFID_QUERY,
        context_value=query_params.context,
        root_value=None,
        variable_values={"hfid": ["Telia"]},
    )

    assert lookup.errors is None
    assert lookup.data
    assert lookup.data["TestingAutonomousSystem"]["edges"] == [
        {"node": {"display_label": "AS1299 - Telia", "hfid": ["Telia"]}}
    ]
