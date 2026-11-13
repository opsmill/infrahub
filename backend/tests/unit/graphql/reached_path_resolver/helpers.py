from __future__ import annotations

from graphql import parse_value

from infrahub.core.constants import RelationshipCardinality, RelationshipDirection
from infrahub.core.regeneration.models import FilterLiteral, PeerFilters, RelationshipHop
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.graphql.analyzer import GraphQLArgument, GraphQLQueryNode

OUT = RelationshipDirection.OUTBOUND


def _rel(name: str, peer: str, identifier: str) -> RelationshipSchema:
    return RelationshipSchema(
        name=name,
        peer=peer,
        identifier=identifier,
        cardinality=RelationshipCardinality.MANY,
        direction=OUT,
        optional=True,
    )


def _node(name: str, *relationships: RelationshipSchema) -> NodeSchema:
    return NodeSchema(
        name=name,
        namespace="Testing",
        generate_profile=False,
        attributes=[AttributeSchema(name="name", kind="Text")],
        relationships=list(relationships),
    )


DEVICE = _node("Device", _rel("interfaces", "TestingInterface", "device__interface"))
INTERFACE = _node("Interface", _rel("addresses", "TestingAddress", "interface__address"))
ADDRESS = _node("Address")
PERSON = _node("Person")
PHYSICAL = _node("Physical")
VIRTUAL = _node("Virtual")
THING = _node("Thing")
ENDPOINT = GenericSchema(
    name="Endpoint",
    namespace="Testing",
    relationships=[_rel("things", "TestingThing", "endpoint__thing")],
)
DEVICE_WITH_GENERIC = _node("Device", _rel("endpoints", "TestingEndpoint", "device__endpoint"))
DEVICE_TWO_OWNERS = _node(
    "Device",
    _rel("primary_owner", "TestingPerson", "device__primary"),
    _rel("backup_owner", "TestingPerson", "device__backup"),
)
DEVICE_WITH_OWNER = _node("Device", _rel("owner", "TestingPerson", "device__owner"))
DEVICE_TWO_GENERIC_RELS = _node(
    "Device",
    _rel("interfaces", "TestingEndpoint", "device__interface"),
    _rel("mgmt_interfaces", "TestingEndpoint", "device__mgmt"),
)
DEVICE_GENERIC_AND_CONCRETE = _node(
    "Device",
    _rel("endpoints", "TestingEndpoint", "device__endpoint"),
    _rel("physical_ports", "TestingPhysical", "device__physical_port"),
)

PHYSICAL_WITH_ADDRESSES = _node("Physical", _rel("addresses", "TestingAddress", "physical__address"))
ENDPOINT_WITH_IMPLEMENTATIONS = GenericSchema(
    name="Endpoint",
    namespace="Testing",
    relationships=[_rel("things", "TestingThing", "endpoint__thing")],
    used_by=["TestingPhysical", "TestingVirtual"],
)

DEVICE_HOP = RelationshipHop(
    node_kind="TestingDevice", relationship_identifier="device__interface", relationship_direction=OUT
)
INTERFACE_HOP = RelationshipHop(
    node_kind="TestingInterface", relationship_identifier="interface__address", relationship_direction=OUT
)
ENDPOINT_HOP = RelationshipHop(
    node_kind="TestingDevice", relationship_identifier="device__endpoint", relationship_direction=OUT
)
PHYSICAL_ADDRESS_HOP = RelationshipHop(
    node_kind="TestingPhysical", relationship_identifier="physical__address", relationship_direction=OUT
)


def _tree(path: str, model: NodeSchema | GenericSchema | None, *children: GraphQLQueryNode) -> GraphQLQueryNode:
    node = GraphQLQueryNode(path=path, infrahub_model=model)
    for child in children:
        child.parent = node
        node.children.append(child)
    return node


def _fragment(model: NodeSchema | GenericSchema, *children: GraphQLQueryNode) -> GraphQLQueryNode:
    node = _tree(model.kind, model, *children)
    node.is_fragment = True
    return node


def _edge_node(*children: GraphQLQueryNode) -> GraphQLQueryNode:
    """The ``edges { node { ... } }`` levels a query places between an object and the fields it selects."""
    return _tree("edges", None, _tree("node", None, *children))


INTERFACE_WITH_FILTERABLE_ATTRIBUTES = NodeSchema(
    name="Interface",
    namespace="Testing",
    generate_profile=False,
    attributes=[
        AttributeSchema(name="name", kind="Text"),
        AttributeSchema(name="status", kind="Text"),
        AttributeSchema(name="role", kind="Text", enum=["uplink", "access"]),
        AttributeSchema(name="enabled", kind="Boolean"),
        AttributeSchema(name="mtu", kind="Number"),
    ],
    relationships=[_rel("device", "TestingDevice", "device__interface")],
)


def _interface_filters(*filters: tuple[str, FilterLiteral]) -> PeerFilters:
    return PeerFilters(relationship_name="interfaces", filters=tuple(filters))


ACTIVE = ("interfaces__status__value", "active")


def _filtered_interfaces(*arguments: GraphQLArgument, children: tuple[GraphQLQueryNode, ...] = ()) -> GraphQLQueryNode:
    interfaces = _tree("interfaces", INTERFACE_WITH_FILTERABLE_ATTRIBUTES, *children)
    interfaces.arguments = list(arguments)
    return interfaces


def _argument(name: str, graphql_value: str) -> GraphQLArgument:
    """An argument as the parser reads it from a query, given the value as written in GraphQL."""
    return GraphQLArgument(name=name, value_node=parse_value(graphql_value))
