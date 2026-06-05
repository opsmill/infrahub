from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.account import ObjectPermission
from infrahub.core.constants import PermissionAction, PermissionDecision
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
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
    # The display label of the node within the event must include the correct label
    # even if the display label contains a related node
    assert event.changelog.display_label == "Ocean Blue"
