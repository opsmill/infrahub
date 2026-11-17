from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.core.regeneration.models import FilterLiteral, PeerFilters


def _prefix_filters(*filters: tuple[str, FilterLiteral]) -> PeerFilters:
    return PeerFilters(relationship_name="prefixes", filters=tuple(filters))


@dataclass(frozen=True, kw_only=True)
class FilteredFieldsCase:
    name: str
    filters: tuple[tuple[str, FilterLiteral], ...]
    expected: frozenset[str]


FILTERED_FIELDS_CASES = [
    FilteredFieldsCase(name="no_filter_selects_on_no_field", filters=(), expected=frozenset()),
    FilteredFieldsCase(
        name="a_value_filter_selects_on_its_attribute",
        filters=(("prefixes__role__value", "aggregate"),),
        expected=frozenset({"role"}),
    ),
    FilteredFieldsCase(
        name="a_values_filter_selects_on_its_attribute",
        filters=(("prefixes__role__values", ("aggregate", "loopback")),),
        expected=frozenset({"role"}),
    ),
    FilteredFieldsCase(
        name="a_property_filter_selects_on_its_attribute",
        filters=(("prefixes__role__is_protected", True),),
        expected=frozenset({"role"}),
    ),
    FilteredFieldsCase(
        name="a_filter_through_a_relationship_selects_on_that_relationship",
        filters=(("prefixes__vrf__name__value", "mgmt"),),
        expected=frozenset({"vrf"}),
    ),
    FilteredFieldsCase(
        name="an_ids_filter_selects_on_no_field",
        filters=(("prefixes__ids", ("p1", "p2")),),
        expected=frozenset(),
    ),
    FilteredFieldsCase(
        name="an_id_filter_selects_on_no_field", filters=(("prefixes__id", "p1"),), expected=frozenset()
    ),
    FilteredFieldsCase(
        name="several_filters_select_on_every_field",
        filters=(
            ("prefixes__role__value", "aggregate"),
            ("prefixes__status__value", "active"),
            ("prefixes__ids", ("p1",)),
        ),
        expected=frozenset({"role", "status"}),
    ),
]


@pytest.mark.parametrize("case", FILTERED_FIELDS_CASES, ids=lambda case: case.name)
def test_filtered_fields(case: FilteredFieldsCase) -> None:
    assert _prefix_filters(*case.filters).filtered_fields == case.expected


@dataclass(frozen=True, kw_only=True)
class QueryFiltersCase:
    name: str
    filters: tuple[tuple[str, FilterLiteral], ...]
    expected: dict[str, Any]


QUERY_FILTERS_CASES = [
    QueryFiltersCase(name="no_filter_gives_an_empty_mapping", filters=(), expected={}),
    QueryFiltersCase(
        name="a_scalar_value_is_passed_as_is",
        filters=(("prefixes__role__value", "aggregate"), ("prefixes__mtu__value", 1500)),
        expected={"prefixes__role__value": "aggregate", "prefixes__mtu__value": 1500},
    ),
    QueryFiltersCase(
        name="a_tuple_of_values_is_passed_as_a_list",
        filters=(("prefixes__role__values", ("aggregate", "loopback")),),
        expected={"prefixes__role__values": ["aggregate", "loopback"]},
    ),
]


@pytest.mark.parametrize("case", QUERY_FILTERS_CASES, ids=lambda case: case.name)
def test_as_query_filters(case: QueryFiltersCase) -> None:
    assert _prefix_filters(*case.filters).as_query_filters() == case.expected
