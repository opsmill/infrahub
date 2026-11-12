from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.constants import RelationshipCardinality, RelationshipKind
from infrahub.core.registry import registry
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql

if TYPE_CHECKING:
    from infrahub.core.branch import Branch

VLAN = NodeSchema(
    name="Vlan",
    namespace="Testing",
    include_in_menu=False,
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
)

DEVICE = NodeSchema(
    name="Device",
    namespace="Testing",
    include_in_menu=False,
    human_friendly_id=["name__value"],
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
)

# The shape of a network interface: a mandatory parent, an optional peer, a uniqueness constraint,
# an HFID and a display label that read the parent's name.
INTERFACE = NodeSchema(
    name="Interface",
    namespace="Testing",
    include_in_menu=False,
    display_label="{{ name__value }} (Device: {{ device__name__value }})",
    human_friendly_id=["device__name__value", "name__value"],
    uniqueness_constraints=[["device", "name__value"]],
    attributes=[
        AttributeSchema(name="name", kind="Text"),
        AttributeSchema(name="speed", kind="Number"),
        AttributeSchema(name="enabled", kind="Boolean", default_value=True),
    ],
    relationships=[
        RelationshipSchema(
            name="device",
            kind=RelationshipKind.PARENT,
            optional=False,
            peer=DEVICE.kind,
            cardinality=RelationshipCardinality.ONE,
        ),
        RelationshipSchema(
            name="vlan",
            kind=RelationshipKind.GENERIC,
            optional=True,
            peer=VLAN.kind,
            cardinality=RelationshipCardinality.ONE,
        ),
    ],
)

CREATE_DEVICE = """
mutation CreateDevice($name: String!) {
    TestingDeviceCreate(data: { name: { value: $name } }) { ok object { id } }
}
"""

CREATE_VLAN = """
mutation CreateVlan($name: String!) {
    TestingVlanCreate(data: { name: { value: $name } }) { ok object { id } }
}
"""

# What the Python SDK sends for `client.create(...)` followed by `save(allow_upsert=True)`:
# the fields by value and the peers by id, no `hfid`, and only `ok` and the id back.
UPSERT_INTERFACE = """
mutation UpsertInterface($name: String!, $device: String!, $vlan: String!) {
    TestingInterfaceUpsert(
        data: {
            name: { value: $name }
            speed: { value: 1000 }
            device: { id: $device }
            vlan: { id: $vlan }
        }
    ) { ok object { id } }
}
"""


@pytest.fixture
def interface_schema(default_branch: Branch, register_core_models_schema: None) -> None:
    registry.schema.register_schema(schema=SchemaRoot(nodes=[VLAN, DEVICE, INTERFACE]), branch=default_branch.name)
    default_branch.update_schema_hash()


@pytest.fixture
def executed_queries(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record the name of every query the database runs, in order, whichever session runs it."""
    names: list[str] = []
    original = InfrahubDatabase.execute_query_with_metadata

    async def record(self: InfrahubDatabase, *args: Any, **kwargs: Any) -> Any:
        names.append(kwargs.get("name") or (args[2] if len(args) > 2 else "undefined"))
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(InfrahubDatabase, "execute_query_with_metadata", record)
    return names


async def _create(db: InfrahubDatabase, branch: Branch, source: str, variables: dict[str, Any]) -> str:
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    result = await graphql(
        schema=gql_params.schema, source=source, context_value=gql_params.context, variable_values=variables
    )
    assert result.errors is None, result.errors
    assert result.data
    return next(iter(result.data.values()))["object"]["id"]


async def test_upsert_of_a_new_node_reads_its_peers_once(
    db: InfrahubDatabase, default_branch: Branch, interface_schema: None, executed_queries: list[str]
) -> None:
    device_id = await _create(db=db, branch=default_branch, source=CREATE_DEVICE, variables={"name": "leaf1"})
    vlan_id = await _create(db=db, branch=default_branch, source=CREATE_VLAN, variables={"name": "servers"})
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    executed_queries.clear()

    result = await graphql(
        schema=gql_params.schema,
        source=UPSERT_INTERFACE,
        context_value=gql_params.context,
        variable_values={"name": "Ethernet1", "device": device_id, "vlan": vlan_id},
    )

    assert result.errors is None, result.errors
    assert result.data
    assert result.data["TestingInterfaceUpsert"]["ok"] is True
    # Both peers come back from one read, which the constraints, the labels and the create all use.
    assert executed_queries == [
        "uniqueness_constraint_validation",
        "node_list_get_info",
        "node_list_get_attribute",
        "node_create_all",
    ]


async def test_upsert_of_an_existing_node_reads_its_new_peer_once(
    db: InfrahubDatabase, default_branch: Branch, interface_schema: None, executed_queries: list[str]
) -> None:
    device_id = await _create(db=db, branch=default_branch, source=CREATE_DEVICE, variables={"name": "leaf1"})
    vlan_id = await _create(db=db, branch=default_branch, source=CREATE_VLAN, variables={"name": "servers"})
    other_vlan_id = await _create(db=db, branch=default_branch, source=CREATE_VLAN, variables={"name": "voice"})
    variables = {"name": "Ethernet1", "device": device_id, "vlan": vlan_id}
    interface_id = await _create(db=db, branch=default_branch, source=UPSERT_INTERFACE, variables=variables)
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    executed_queries.clear()

    result = await graphql(
        schema=gql_params.schema,
        source=UPSERT_INTERFACE,
        context_value=gql_params.context,
        variable_values={**variables, "vlan": other_vlan_id},
    )

    assert result.errors is None, result.errors
    assert result.data
    assert result.data["TestingInterfaceUpsert"]["object"]["id"] == interface_id
    assert executed_queries == [
        # The create attempt stops at the uniqueness check, which finds the existing node.
        "uniqueness_constraint_validation",
        # The existing node, read for the mutation and again for the lock preview.
        "node_list_get_info",
        "node_list_get_attribute",
        "node_list_get_info",
        "node_list_get_attribute",
        # The stored peers of both relationships, then the new peer once.
        "relationship_get_peer",
        "relationship_get_peer",
        "node_list_get_info",
        "node_list_get_attribute",
        # The profiles of the node.
        "relationship_get_peer",
        # One read per saved attribute, the relationship swap, the recomputed HFID and display label.
        "node_list_get_attribute",
        "node_list_get_attribute",
        "relationship_delete",
        "relationship_create",
        "node_list_get_attribute",
        "node_list_get_attribute",
        "node_update_metadata",
    ]
