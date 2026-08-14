from __future__ import annotations

from infrahub.core.constants import RelationshipCardinality, RelationshipDirection
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.graphql.analyzer import GraphQLQueryNode, ReachedPath, ReachedPathResolver, RelationshipHop

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
ENDPOINT = GenericSchema(name="Endpoint", namespace="Testing")
DEVICE_WITH_GENERIC = _node("Device", _rel("endpoints", "TestingEndpoint", "device__endpoint"))
DEVICE_TWO_OWNERS = _node(
    "Device",
    _rel("primary_owner", "TestingPerson", "device__primary"),
    _rel("backup_owner", "TestingPerson", "device__backup"),
)
DEVICE_WITH_OWNER = _node("Device", _rel("owner", "TestingPerson", "device__owner"))

DEVICE_HOP = RelationshipHop(
    node_kind="TestingDevice", relationship_identifier="device__interface", relationship_direction=OUT
)
INTERFACE_HOP = RelationshipHop(
    node_kind="TestingInterface", relationship_identifier="interface__address", relationship_direction=OUT
)


def _tree(path: str, model: NodeSchema | GenericSchema | None, *children: GraphQLQueryNode) -> GraphQLQueryNode:
    node = GraphQLQueryNode(path=path, infrahub_model=model)
    for child in children:
        child.parent = node
        node.children.append(child)
    return node


def test_single_hop_narrows_to_the_owning_root() -> None:
    tree = _tree("TestingDevice", DEVICE, _tree("interfaces", INTERFACE))

    result = ReachedPathResolver(queries=[tree]).resolve()

    assert result == {"TestingInterface": ReachedPath(hops=(DEVICE_HOP,))}


def test_multi_hop_records_the_full_chain_deepest_first() -> None:
    tree = _tree("TestingDevice", DEVICE, _tree("interfaces", INTERFACE, _tree("addresses", ADDRESS)))

    result = ReachedPathResolver(queries=[tree]).resolve()

    assert result == {
        "TestingInterface": ReachedPath(hops=(DEVICE_HOP,)),
        "TestingAddress": ReachedPath(hops=(INTERFACE_HOP, DEVICE_HOP)),
    }


def test_generic_peer_widens() -> None:
    tree = _tree("TestingDevice", DEVICE_WITH_GENERIC, _tree("endpoints", ENDPOINT))

    result = ReachedPathResolver(queries=[tree]).resolve()

    assert result == {}


def test_field_that_is_not_a_relationship_on_its_owner_widens() -> None:
    # A node carrying a model whose path is not a relationship on its owner (an inline/named fragment
    # refinement) cannot be pinned to a reverse relationship.
    tree = _tree("TestingDevice", DEVICE, _tree("TestingConcrete", PERSON))

    result = ReachedPathResolver(queries=[tree]).resolve()

    assert result == {}


def test_kind_reached_by_more_than_one_chain_widens() -> None:
    tree = _tree(
        "TestingDevice",
        DEVICE_TWO_OWNERS,
        _tree("primary_owner", PERSON),
        _tree("backup_owner", PERSON),
    )

    result = ReachedPathResolver(queries=[tree]).resolve()

    assert result == {}


def test_kind_read_at_a_root_and_through_a_relationship_widens() -> None:
    device_tree = _tree("TestingDevice", DEVICE_WITH_OWNER, _tree("owner", PERSON))
    person_root = _tree("TestingPerson", PERSON)

    result = ReachedPathResolver(queries=[device_tree, person_root]).resolve()

    assert result == {}


def test_a_query_without_traversal_resolves_nothing() -> None:
    tree = _tree("TestingDevice", DEVICE)

    result = ReachedPathResolver(queries=[tree]).resolve()

    assert result == {}
