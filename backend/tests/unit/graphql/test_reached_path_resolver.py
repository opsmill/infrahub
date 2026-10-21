from __future__ import annotations

from dataclasses import dataclass

import pytest
from graphql import parse_value

from infrahub.core.constants import RelationshipCardinality, RelationshipDirection
from infrahub.core.regeneration.models import FilterLiteral, PeerFilters, ReachedPath, RelationshipHop, RelationshipRead
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.graphql.analyzer import GraphQLArgument, GraphQLQueryNode, ReachedPathResolver

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
    # A node carrying a model whose path is neither a relationship on its owner nor a fragment cannot
    # be pinned to a reverse relationship.
    tree = _tree("TestingDevice", DEVICE, _tree("TestingConcrete", PERSON))

    result = ReachedPathResolver(queries=[tree]).resolve()

    assert result == {}


def test_a_relationship_inside_a_fragment_on_a_peer_keeps_the_chain_through_the_fragment() -> None:
    addresses = _tree("addresses", ADDRESS)
    endpoints = _tree("endpoints", ENDPOINT, _edge_node(_fragment(PHYSICAL_WITH_ADDRESSES, addresses)))
    endpoints.infrahub_node_models = [PHYSICAL_WITH_ADDRESSES, VIRTUAL]
    tree = _tree("TestingDevice", DEVICE_WITH_GENERIC, endpoints)

    result = ReachedPathResolver(queries=[tree]).resolve()

    assert result == {
        "TestingPhysical": (ReachedPath(hops=(ENDPOINT_HOP,)),),
        "TestingVirtual": (ReachedPath(hops=(ENDPOINT_HOP,)),),
        "TestingAddress": (ReachedPath(hops=(PHYSICAL_ADDRESS_HOP, ENDPOINT_HOP)),),
    }


def test_a_fragment_on_a_generic_resolves_to_its_implementations() -> None:
    things = _tree("things", THING)
    fragment = _fragment(ENDPOINT_WITH_IMPLEMENTATIONS, things)
    tree = _tree("TestingDevice", DEVICE_WITH_GENERIC, _tree("endpoints", ENDPOINT, _edge_node(fragment)))

    result = ReachedPathResolver(queries=[tree]).resolve()

    thing_hop = RelationshipHop(
        node_kind="TestingEndpoint", relationship_identifier="endpoint__thing", relationship_direction=OUT
    )
    assert result == {
        "TestingPhysical": (ReachedPath(hops=(ENDPOINT_HOP,)),),
        "TestingVirtual": (ReachedPath(hops=(ENDPOINT_HOP,)),),
        "TestingThing": (ReachedPath(hops=(thing_hop, ENDPOINT_HOP)),),
    }


def test_a_relationship_inside_a_fragment_on_the_root_narrows_like_one_outside_it() -> None:
    # The fragment stands for the root device itself, so the device maps to itself through an empty chain.
    tree = _tree("TestingDevice", DEVICE, _edge_node(_fragment(DEVICE, _tree("interfaces", INTERFACE))))

    result = ReachedPathResolver(queries=[tree]).resolve()

    assert result == {
        "TestingDevice": (ReachedPath(hops=()),),
        "TestingInterface": (ReachedPath(hops=(DEVICE_HOP,)),),
    }


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


def test_kind_read_at_a_root_and_through_a_relationship_keeps_an_empty_chain_besides_its_chains() -> None:
    device_tree = _tree("TestingDevice", DEVICE_WITH_OWNER, _tree("owner", PERSON))
    person_root = _tree("TestingPerson", PERSON)

    result = ReachedPathResolver(queries=[device_tree, person_root]).resolve()

    owner_hop = RelationshipHop(
        node_kind="TestingDevice", relationship_identifier="device__owner", relationship_direction=OUT
    )
    assert result == {"TestingPerson": (ReachedPath(hops=()), ReachedPath(hops=(owner_hop,)))}


def test_kind_read_at_a_root_and_reached_un_pinnably_widens() -> None:
    device_tree = _tree("TestingDevice", DEVICE_WITH_OWNER, _tree("owner", PERSON), _tree("TestingConcrete", PERSON))
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
    # PHYSICAL is also reached by a node whose path is neither a relationship on the device nor a
    # fragment, which cannot be pinned -- so PHYSICAL widens even though the generic peer resolves it.
    unpinnable = _tree("TestingPhysical", PHYSICAL)
    tree = _tree("TestingDevice", DEVICE_WITH_GENERIC, endpoints, unpinnable)

    result = ReachedPathResolver(queries=[tree]).resolve()

    endpoint_hop = RelationshipHop(
        node_kind="TestingDevice", relationship_identifier="device__endpoint", relationship_direction=OUT
    )
    assert result == {"TestingVirtual": (ReachedPath(hops=(endpoint_hop,)),)}


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


def _interface_hop_filters(*roots: GraphQLQueryNode) -> PeerFilters | None:
    paths = ReachedPathResolver(queries=list(roots)).resolve()["TestingInterface"]
    return paths[0].hops[0].peer_filters


@dataclass(frozen=True, kw_only=True)
class HopFilterCase:
    name: str
    arguments: tuple[GraphQLArgument, ...]
    expected: PeerFilters | None


HOP_FILTER_CASES = [
    HopFilterCase(
        name="a_constant_filter_is_recorded",
        arguments=(_argument("status__value", '"active"'),),
        expected=_interface_filters(ACTIVE),
    ),
    HopFilterCase(
        name="an_enum_name_is_left_out_as_the_resolver_receives_the_value",
        arguments=(
            _argument("role__value", "UPLINK"),
            _argument("status__value", '"active"'),
        ),
        expected=_interface_filters(ACTIVE),
    ),
    HopFilterCase(
        name="a_text_value_on_an_enum_attribute_is_recorded",
        arguments=(_argument("role__value", '"uplink"'),),
        expected=_interface_filters(("interfaces__role__value", "uplink")),
    ),
    HopFilterCase(
        name="a_false_filter_value_is_left_out_as_the_relationship_resolver_ignores_it",
        arguments=(_argument("enabled__value", "false"), _argument("status__value", '"active"')),
        expected=_interface_filters(ACTIVE),
    ),
    HopFilterCase(
        name="a_zero_filter_value_is_left_out_as_the_relationship_resolver_ignores_it",
        arguments=(_argument("mtu__value", "0"), _argument("status__value", '"active"')),
        expected=_interface_filters(ACTIVE),
    ),
    HopFilterCase(
        name="an_empty_text_filter_value_is_left_out_as_the_relationship_resolver_ignores_it",
        arguments=(_argument("name__value", '""'), _argument("status__value", '"active"')),
        expected=_interface_filters(ACTIVE),
    ),
    HopFilterCase(
        name="only_false_values_record_no_filter",
        arguments=(_argument("enabled__value", "false"),),
        expected=None,
    ),
    HopFilterCase(
        name="a_list_of_values_holding_a_false_value_is_recorded_as_given",
        arguments=(_argument("mtu__values", "[0, 1500]"),),
        expected=_interface_filters(("interfaces__mtu__values", (0, 1500))),
    ),
    HopFilterCase(
        name="a_true_value_is_recorded",
        arguments=(_argument("enabled__value", "true"),),
        expected=_interface_filters(("interfaces__enabled__value", True)),
    ),
    HopFilterCase(
        name="an_attribute_property_filter_is_recorded",
        arguments=(_argument("status__is_protected", "true"),),
        expected=_interface_filters(("interfaces__status__is_protected", True)),
    ),
    HopFilterCase(
        name="an_ids_filter_is_recorded_even_when_empty",
        arguments=(_argument("ids", "[]"),),
        expected=_interface_filters(("interfaces__ids", ())),
    ),
    HopFilterCase(
        name="an_argument_the_resolver_does_not_filter_on_is_left_out",
        arguments=(_argument("limit", "5"), _argument("isnull", "true")),
        expected=None,
    ),
    HopFilterCase(
        name="a_display_label_filter_is_left_out_as_its_value_can_change_with_other_nodes",
        arguments=(_argument("display_label__value", '"eth0"'), _argument("status__value", '"active"')),
        expected=_interface_filters(ACTIVE),
    ),
    HopFilterCase(
        name="a_filter_from_a_variable_is_left_out",
        arguments=(_argument("status__value", "$status"),),
        expected=None,
    ),
    HopFilterCase(
        name="a_value_the_peer_query_rejects_is_left_out",
        arguments=(_argument("mtu__value", "1.5"), _argument("status__value", '"active"')),
        expected=_interface_filters(ACTIVE),
    ),
]


@pytest.mark.parametrize("case", HOP_FILTER_CASES, ids=lambda case: case.name)
def test_the_filters_a_hop_carries(case: HopFilterCase) -> None:
    tree = _tree("TestingDevice", DEVICE, _filtered_interfaces(*case.arguments))

    assert _interface_hop_filters(tree) == case.expected


@dataclass(frozen=True, kw_only=True)
class OtherReadCase:
    name: str
    root_arguments: tuple[GraphQLArgument, ...] = ()
    interface_arguments: tuple[GraphQLArgument, ...] = ()
    other_fields: tuple[str, ...] = ()


OTHER_READ_CASES = [
    OtherReadCase(
        name="a_filter_through_a_relationship_of_the_root",
        root_arguments=(_argument("interfaces__name__value", '"eth0"'),),
    ),
    OtherReadCase(
        name="a_filter_through_a_relationship_of_the_filtered_peers",
        interface_arguments=(_argument("device__name__value", '"spine-1"'),),
    ),
    OtherReadCase(
        name="a_read_that_includes_the_descendants",
        interface_arguments=(_argument("include_descendants", "true"),),
    ),
    OtherReadCase(name="a_read_of_the_descendants", other_fields=("descendants",)),
    OtherReadCase(name="a_read_of_the_ancestors", other_fields=("ancestors",)),
]


@pytest.mark.parametrize("case", OTHER_READ_CASES, ids=lambda case: case.name)
def test_a_query_reading_peers_another_way_records_no_filter(case: OtherReadCase) -> None:
    interfaces = _filtered_interfaces(_argument("status__value", '"active"'), *case.interface_arguments)
    tree = _tree("TestingDevice", DEVICE, interfaces, *(_tree(field_name, None) for field_name in case.other_fields))
    tree.arguments = list(case.root_arguments)
    resolver = ReachedPathResolver(queries=[tree])

    assert all(hop.peer_filters is None for paths in resolver.resolve().values() for path in paths for hop in path.hops)
    assert all(read.peer_filters is None for read in resolver.relationship_reads())


def _read(
    owner_kind: str,
    relationship_name: str,
    identifier: str,
    peer_kinds: set[str],
    peer_filters: PeerFilters | None = None,
) -> RelationshipRead:
    return RelationshipRead(
        owner_kind=owner_kind,
        relationship_name=relationship_name,
        relationship_identifier=identifier,
        relationship_direction=OUT,
        peer_kinds=frozenset(peer_kinds),
        peer_filters=peer_filters,
    )


DEVICE_INTERFACES_READ = _read("TestingDevice", "interfaces", "device__interface", {"TestingInterface"})
DEVICE_WITHOUT_IDENTIFIER = _node(
    "Device",
    RelationshipSchema(
        name="interfaces",
        peer="TestingInterface",
        cardinality=RelationshipCardinality.MANY,
        direction=OUT,
        optional=True,
    ),
)


def _generic_endpoints(*children: GraphQLQueryNode) -> GraphQLQueryNode:
    endpoints = _tree("endpoints", ENDPOINT_WITH_IMPLEMENTATIONS, *children)
    endpoints.infrahub_node_models = [PHYSICAL_WITH_ADDRESSES, VIRTUAL]
    return endpoints


@dataclass(frozen=True, kw_only=True)
class RelationshipReadCase:
    name: str
    tree: GraphQLQueryNode
    expected: tuple[RelationshipRead, ...]


RELATIONSHIP_READ_CASES = [
    RelationshipReadCase(
        name="a_read_under_structural_levels_counts_for_the_nearest_object",
        tree=_tree("TestingDevice", DEVICE, _edge_node(_tree("interfaces", INTERFACE))),
        expected=(DEVICE_INTERFACES_READ,),
    ),
    RelationshipReadCase(
        name="a_read_on_a_generic_owner_counts_for_each_implementation",
        tree=_tree("TestingDevice", DEVICE_WITH_GENERIC, _generic_endpoints(_tree("things", THING))),
        expected=(
            _read("TestingDevice", "endpoints", "device__endpoint", {"TestingPhysical", "TestingVirtual"}),
            _read("TestingPhysical", "things", "endpoint__thing", {"TestingThing"}),
            _read("TestingVirtual", "things", "endpoint__thing", {"TestingThing"}),
        ),
    ),
    RelationshipReadCase(
        name="a_read_inside_a_fragment_counts_for_the_fragment_kind_only",
        tree=_tree(
            "TestingDevice",
            DEVICE_WITH_GENERIC,
            _generic_endpoints(_fragment(PHYSICAL_WITH_ADDRESSES, _tree("addresses", ADDRESS))),
        ),
        expected=(
            _read("TestingDevice", "endpoints", "device__endpoint", {"TestingPhysical", "TestingVirtual"}),
            _read("TestingPhysical", "addresses", "physical__address", {"TestingAddress"}),
        ),
    ),
    RelationshipReadCase(
        name="a_relationship_read_twice_with_the_same_filters_counts_once",
        tree=_tree(
            "TestingDevice",
            DEVICE,
            _filtered_interfaces(_argument("status__value", '"active"')),
            _filtered_interfaces(_argument("status__value", '"active"')),
        ),
        expected=(
            _read("TestingDevice", "interfaces", "device__interface", {"TestingInterface"}, _interface_filters(ACTIVE)),
        ),
    ),
    RelationshipReadCase(
        name="a_relationship_read_with_and_without_filters_counts_twice",
        tree=_tree(
            "TestingDevice",
            DEVICE,
            _filtered_interfaces(_argument("status__value", '"active"')),
            _filtered_interfaces(),
        ),
        expected=(
            DEVICE_INTERFACES_READ,
            _read("TestingDevice", "interfaces", "device__interface", {"TestingInterface"}, _interface_filters(ACTIVE)),
        ),
    ),
    RelationshipReadCase(
        name="a_field_that_is_not_a_relationship_of_its_owner_is_not_a_read",
        tree=_tree("TestingDevice", DEVICE, _tree("uplinks", INTERFACE)),
        expected=(),
    ),
    RelationshipReadCase(
        name="a_relationship_without_an_identifier_is_not_a_read",
        tree=_tree("TestingDevice", DEVICE_WITHOUT_IDENTIFIER, _tree("interfaces", INTERFACE)),
        expected=(),
    ),
]


@pytest.mark.parametrize("case", RELATIONSHIP_READ_CASES, ids=lambda case: case.name)
def test_relationship_reads(case: RelationshipReadCase) -> None:
    assert ReachedPathResolver(queries=[case.tree]).relationship_reads() == case.expected
