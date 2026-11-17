from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.core.constants import RelationshipCardinality
from infrahub.core.regeneration.models import PeerFilters, RelationshipRead
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.graphql.analyzer import GraphQLQueryNode, ReachedPathResolver

from .helpers import (
    ACTIVE,
    ADDRESS,
    DEVICE,
    DEVICE_WITH_GENERIC,
    ENDPOINT_WITH_IMPLEMENTATIONS,
    INTERFACE,
    OUT,
    PHYSICAL_WITH_ADDRESSES,
    THING,
    VIRTUAL,
    _argument,
    _edge_node,
    _filtered_interfaces,
    _fragment,
    _interface_filters,
    _node,
    _tree,
)


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
    # TestingDevice { edges { node { interfaces } } }
    RelationshipReadCase(
        name="a_read_under_structural_levels_is_recorded_for_the_nearest_object",
        tree=_tree("TestingDevice", DEVICE, _edge_node(_tree("interfaces", INTERFACE))),
        expected=(DEVICE_INTERFACES_READ,),
    ),
    # TestingDevice { endpoints { things } }, endpoints on the generic TestingEndpoint
    RelationshipReadCase(
        name="a_read_on_a_generic_owner_is_recorded_once_per_implementation",
        tree=_tree("TestingDevice", DEVICE_WITH_GENERIC, _generic_endpoints(_tree("things", THING))),
        expected=(
            _read("TestingDevice", "endpoints", "device__endpoint", {"TestingPhysical", "TestingVirtual"}),
            _read("TestingPhysical", "things", "endpoint__thing", {"TestingThing"}),
            _read("TestingVirtual", "things", "endpoint__thing", {"TestingThing"}),
        ),
    ),
    # TestingDevice { endpoints { ... on TestingPhysical { addresses } } }
    RelationshipReadCase(
        name="a_read_inside_a_fragment_is_recorded_for_the_fragment_kind_only",
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
    # TestingDevice { interfaces(status__value: "active") interfaces(status__value: "active") }
    RelationshipReadCase(
        name="a_relationship_read_twice_with_the_same_filters_is_recorded_once",
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
    # TestingDevice { interfaces(status__value: "active") interfaces }
    RelationshipReadCase(
        name="a_relationship_read_with_and_without_filters_is_recorded_twice",
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
    # TestingDevice { uplinks }
    RelationshipReadCase(
        name="a_field_that_is_not_a_relationship_of_its_owner_is_not_a_read",
        tree=_tree("TestingDevice", DEVICE, _tree("uplinks", INTERFACE)),
        expected=(),
    ),
    # TestingDevice { interfaces }, interfaces without an identifier
    RelationshipReadCase(
        name="a_relationship_without_an_identifier_is_not_a_read",
        tree=_tree("TestingDevice", DEVICE_WITHOUT_IDENTIFIER, _tree("interfaces", INTERFACE)),
        expected=(),
    ),
]


@pytest.mark.parametrize("case", RELATIONSHIP_READ_CASES, ids=lambda case: case.name)
def test_relationship_reads(case: RelationshipReadCase) -> None:
    assert ReachedPathResolver(queries=[case.tree]).relationship_reads() == case.expected
