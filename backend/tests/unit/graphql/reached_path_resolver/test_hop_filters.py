from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.graphql.analyzer import GraphQLArgument, GraphQLQueryNode, ReachedPathResolver

from .helpers import (
    ACTIVE,
    DEVICE,
    _argument,
    _filtered_interfaces,
    _interface_filters,
    _tree,
)

if TYPE_CHECKING:
    from infrahub.core.regeneration.models import PeerFilters


def _interface_hop_filters(*roots: GraphQLQueryNode) -> PeerFilters | None:
    paths = ReachedPathResolver(queries=list(roots)).resolve()["TestingInterface"]
    return paths[0].hops[0].peer_filters


@dataclass(frozen=True, kw_only=True)
class HopFilterCase:
    name: str
    arguments: tuple[GraphQLArgument, ...]
    expected: PeerFilters | None


# Each case reads TestingDevice { interfaces(<arguments>) }.
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
    # TestingDevice(interfaces__name__value: "eth0") { interfaces(status__value: "active") }
    OtherReadCase(
        name="a_filter_through_a_relationship_of_the_root",
        root_arguments=(_argument("interfaces__name__value", '"eth0"'),),
    ),
    # TestingDevice { interfaces(status__value: "active", device__name__value: "spine-1") }
    OtherReadCase(
        name="a_filter_through_a_relationship_of_the_filtered_peers",
        interface_arguments=(_argument("device__name__value", '"spine-1"'),),
    ),
    # TestingDevice { interfaces(status__value: "active", include_descendants: true) }
    OtherReadCase(
        name="a_read_that_includes_the_descendants",
        interface_arguments=(_argument("include_descendants", "true"),),
    ),
    # TestingDevice(interfaces__isnull: false) { interfaces(status__value: "active") }
    OtherReadCase(
        name="an_isnull_filter_on_a_relationship_of_the_root",
        root_arguments=(_argument("interfaces__isnull", "false"),),
    ),
    # TestingDevice(interfaces__ids: ["intf1"]) { interfaces(status__value: "active") }
    OtherReadCase(
        name="an_ids_filter_on_a_relationship_of_the_root",
        root_arguments=(_argument("interfaces__ids", '["intf1"]'),),
    ),
    # TestingDevice { interfaces(status__value: "active", device__ids: ["dev1"]) }
    OtherReadCase(
        name="an_ids_filter_on_a_relationship_of_the_filtered_peers",
        interface_arguments=(_argument("device__ids", '["dev1"]'),),
    ),
    # TestingDevice { interfaces(status__value: "active") descendants }
    OtherReadCase(name="a_read_of_the_descendants", other_fields=("descendants",)),
    # TestingDevice { interfaces(status__value: "active") ancestors }
    OtherReadCase(name="a_read_of_the_ancestors", other_fields=("ancestors",)),
]


@pytest.mark.parametrize("case", OTHER_READ_CASES, ids=lambda case: case.name)
def test_a_query_selecting_peers_through_a_related_node_or_a_hierarchy_records_no_filter(case: OtherReadCase) -> None:
    interfaces = _filtered_interfaces(_argument("status__value", '"active"'), *case.interface_arguments)
    tree = _tree("TestingDevice", DEVICE, interfaces, *(_tree(field_name, None) for field_name in case.other_fields))
    tree.arguments = list(case.root_arguments)
    resolver = ReachedPathResolver(queries=[tree])

    assert all(hop.peer_filters is None for paths in resolver.resolve().values() for path in paths for hop in path.hops)
    assert all(read.peer_filters is None for read in resolver.relationship_reads())
