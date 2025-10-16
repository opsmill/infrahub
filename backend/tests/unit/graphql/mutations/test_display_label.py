from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from infrahub.core.account import GlobalPermission, ObjectPermission
from infrahub.core.branch.models import Branch
from infrahub.core.constants import GlobalPermissions, PermissionAction, PermissionDecision
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.services import InfrahubServices
from tests.adapters.event import MemoryInfrahubEvent
from tests.helpers.graphql import graphql
from tests.helpers.permissions import define_permissions
from tests.helpers.schema import COLOR, TSHIRT

if TYPE_CHECKING:
    from infrahub.auth import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


async def test_update_display_label_missing_kind(
    db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch
) -> None:
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=UPDATE_DISPLAY_LABEL,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": str(uuid4()), "kind": "InvalidNodeKind", "value": "very-new-label"},
    )
    assert result.errors
    assert "Unable to find the schema 'InvalidNodeKind' in the registry" in str(result.errors)


async def test_update_display_label_not_defined(
    db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch
) -> None:
    SCHEMA: dict[str, Any] = {
        "generics": [],
        "nodes": [
            {
                "name": "Widget",
                "namespace": "Testing",
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "label", "kind": "Text", "optional": True},
                    {"name": "description", "kind": "Text", "optional": True},
                ],
            },
        ],
    }

    schema = SchemaRoot(**SCHEMA)

    registry.schema.register_schema(schema=schema, branch=default_branch.name)
    default_branch.update_schema_hash()

    query_kind = "TestingWidget"
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=UPDATE_DISPLAY_LABEL,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": str(uuid4()), "kind": query_kind, "value": "very-new-label"},
    )
    assert result.errors
    assert f"{query_kind}.display_label has not been defined for this kind" in str(result.errors)


async def test_update_display_label_update(
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
        source=UPDATE_DISPLAY_LABEL,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": str(uuid4()), "kind": TSHIRT.kind, "value": "very-new-label"},
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
    assert before_change.data["TestingTShirt"]["edges"][0]["node"]["display_label"] == "Ocean Blue"

    existing_node = await graphql(
        schema=gql_params.schema,
        source=UPDATE_DISPLAY_LABEL,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": t1.get_id(), "kind": TSHIRT.kind, "value": "very-new-label"},
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
    assert after_change.data["TestingTShirt"]["edges"][0]["node"]["display_label"] == "very-new-label"


UPDATE_DISPLAY_LABEL = """
mutation UpdateDisplayLabel(
  $id: String!
  $kind: String!
  $value: String!
) {
  InfrahubUpdateDisplayLabel(data: {id: $id, kind: $kind, value: $value}) {
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
            }
        }
    }
}
"""
