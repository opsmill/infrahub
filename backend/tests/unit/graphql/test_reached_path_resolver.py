from __future__ import annotations

from infrahub.core.constants import RelationshipCardinality, RelationshipDirection
from infrahub.core.regeneration.models import ReachedPath, RelationshipHop
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.graphql.analyzer import GraphQLQueryNode, ReachedPathResolver

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

    assert result == {"TestingInterface": (ReachedPath(hops=(DEVICE_HOP,)),)}


def test_multi_hop_records_the_full_chain_deepest_first() -> None:
    tree = _tree("TestingDevice", DEVICE, _tree("interfaces", INTERFACE, _tree("addresses", ADDRESS)))

    result = ReachedPathResolver(queries=[tree]).resolve()

    assert result == {
        "TestingInterface": (ReachedPath(hops=(DEVICE_HOP,)),),
        "TestingAddress": (ReachedPath(hops=(INTERFACE_HOP, DEVICE_HOP)),),
    }


def test_generic_peer_resolves_to_its_concrete_implementations() -> None:
    endpoints = _tree("endpoints", ENDPOINT)
    endpoints.infrahub_node_models = [PHYSICAL, VIRTUAL]
    tree = _tree("TestingDevice", DEVICE_WITH_GENERIC, endpoints)

    result = ReachedPathResolver(queries=[tree]).resolve()

    endpoint_hop = RelationshipHop(
        node_kind="TestingDevice", relationship_identifier="device__endpoint", relationship_direction=OUT
    )
    assert result == {
        "TestingPhysical": (ReachedPath(hops=(endpoint_hop,)),),
        "TestingVirtual": (ReachedPath(hops=(endpoint_hop,)),),
    }


def test_field_that_is_not_a_relationship_on_its_owner_widens() -> None:
    # A node carrying a model whose path is not a relationship on its owner (an inline/named fragment
    # refinement) cannot be pinned to a reverse relationship.
    tree = _tree("TestingDevice", DEVICE, _tree("TestingConcrete", PERSON))

    result = ReachedPathResolver(queries=[tree]).resolve()

    assert result == {}


def test_kind_reached_by_more_than_one_chain_keeps_every_chain() -> None:
    tree = _tree(
        "TestingDevice",
        DEVICE_TWO_OWNERS,
        _tree("primary_owner", PERSON),
        _tree("backup_owner", PERSON),
    )

    result = ReachedPathResolver(queries=[tree]).resolve()

    backup_hop = RelationshipHop(
        node_kind="TestingDevice", relationship_identifier="device__backup", relationship_direction=OUT
    )
    primary_hop = RelationshipHop(
        node_kind="TestingDevice", relationship_identifier="device__primary", relationship_direction=OUT
    )
    assert result == {"TestingPerson": (ReachedPath(hops=(backup_hop,)), ReachedPath(hops=(primary_hop,)))}


def test_kind_read_at_a_root_and_through_a_relationship_widens() -> None:
    device_tree = _tree("TestingDevice", DEVICE_WITH_OWNER, _tree("owner", PERSON))
    person_root = _tree("TestingPerson", PERSON)

    result = ReachedPathResolver(queries=[device_tree, person_root]).resolve()

    assert result == {}


def test_a_query_without_traversal_resolves_nothing() -> None:
    tree = _tree("TestingDevice", DEVICE)

    result = ReachedPathResolver(queries=[tree]).resolve()

    assert result == {}


def test_generic_peer_reached_by_two_relationships_keeps_both_chains_per_implementation() -> None:
    interfaces = _tree("interfaces", ENDPOINT)
    interfaces.infrahub_node_models = [PHYSICAL, VIRTUAL]
    mgmt_interfaces = _tree("mgmt_interfaces", ENDPOINT)
    mgmt_interfaces.infrahub_node_models = [PHYSICAL, VIRTUAL]
    tree = _tree("TestingDevice", DEVICE_TWO_GENERIC_RELS, interfaces, mgmt_interfaces)

    result = ReachedPathResolver(queries=[tree]).resolve()

    interface_hop = RelationshipHop(
        node_kind="TestingDevice", relationship_identifier="device__interface", relationship_direction=OUT
    )
    mgmt_hop = RelationshipHop(
        node_kind="TestingDevice", relationship_identifier="device__mgmt", relationship_direction=OUT
    )
    both = (ReachedPath(hops=(interface_hop,)), ReachedPath(hops=(mgmt_hop,)))
    assert result == {"TestingPhysical": both, "TestingVirtual": both}


def test_a_kind_reached_via_a_generic_peer_and_a_concrete_relationship_unions_the_chains() -> None:
    endpoints = _tree("endpoints", ENDPOINT)
    endpoints.infrahub_node_models = [PHYSICAL, VIRTUAL]
    physical_ports = _tree("physical_ports", PHYSICAL)
    tree = _tree("TestingDevice", DEVICE_GENERIC_AND_CONCRETE, endpoints, physical_ports)

    result = ReachedPathResolver(queries=[tree]).resolve()

    endpoint_hop = RelationshipHop(
        node_kind="TestingDevice", relationship_identifier="device__endpoint", relationship_direction=OUT
    )
    port_hop = RelationshipHop(
        node_kind="TestingDevice", relationship_identifier="device__physical_port", relationship_direction=OUT
    )
    assert result == {
        "TestingPhysical": (ReachedPath(hops=(endpoint_hop,)), ReachedPath(hops=(port_hop,))),
        "TestingVirtual": (ReachedPath(hops=(endpoint_hop,)),),
    }


def test_a_kind_reached_through_a_relationship_on_a_generic_owner_narrows() -> None:
    # A kind reached through a relationship defined on a generic owner pins to the generic kind: the
    # relationship carries one identifier and every instance is labelled with the generic, so the
    # reverse traversal keyed on the generic label reaches every owner. The generic peer's own
    # implementations narrow alongside, matched by uuid.
    things = _tree("things", THING)
    endpoints = _tree("endpoints", ENDPOINT, things)
    endpoints.infrahub_node_models = [PHYSICAL, VIRTUAL]
    tree = _tree("TestingDevice", DEVICE_WITH_GENERIC, endpoints)

    result = ReachedPathResolver(queries=[tree]).resolve()

    device_hop = RelationshipHop(
        node_kind="TestingDevice", relationship_identifier="device__endpoint", relationship_direction=OUT
    )
    endpoint_hop = RelationshipHop(
        node_kind="TestingEndpoint", relationship_identifier="endpoint__thing", relationship_direction=OUT
    )
    assert result == {
        "TestingPhysical": (ReachedPath(hops=(device_hop,)),),
        "TestingVirtual": (ReachedPath(hops=(device_hop,)),),
        "TestingThing": (ReachedPath(hops=(endpoint_hop, device_hop)),),
    }


def test_an_implementation_also_reached_un_pinnably_widens_while_its_siblings_narrow() -> None:
    endpoints = _tree("endpoints", ENDPOINT)
    endpoints.infrahub_node_models = [PHYSICAL, VIRTUAL]
    # PHYSICAL is also reached by a node whose path is not a relationship on the device (a fragment
    # refinement), which cannot be pinned -- so PHYSICAL widens even though the generic peer resolves it.
    refinement = _tree("TestingPhysical", PHYSICAL)
    tree = _tree("TestingDevice", DEVICE_WITH_GENERIC, endpoints, refinement)

    result = ReachedPathResolver(queries=[tree]).resolve()

    endpoint_hop = RelationshipHop(
        node_kind="TestingDevice", relationship_identifier="device__endpoint", relationship_direction=OUT
    )
    assert result == {"TestingVirtual": (ReachedPath(hops=(endpoint_hop,)),)}
