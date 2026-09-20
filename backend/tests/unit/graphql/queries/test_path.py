from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

import pytest

from infrahub.core.schema import NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.graphql.queries.path import select_hop_relationships
from tests.constants import TestKind
from tests.helpers.schema import CONTINENT, COUNTRY, LOCATION, SITE

PLAIN_IDENTIFIER = "country__managed_site"


def _location_variant(name: str, parent: str | None, children: str | None) -> NodeSchema:
    node = deepcopy(CONTINENT)
    node.name = name
    node.parent = parent
    node.children = children
    return node


def _processed_branch(nodes: list[NodeSchema]) -> SchemaBranch:
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(generics=[deepcopy(LOCATION)], nodes=nodes))
    schema_branch.process()
    return schema_branch


@pytest.fixture
def location_schema_branch() -> SchemaBranch:
    country = deepcopy(COUNTRY)
    country.relationships.append(
        RelationshipSchema(name="managed_sites", peer=TestKind.SITE, identifier=PLAIN_IDENTIFIER, optional=True)
    )
    site = deepcopy(SITE)
    site.relationships.append(
        RelationshipSchema(name="managed_by", peer=TestKind.COUNTRY, identifier=PLAIN_IDENTIFIER, optional=True)
    )
    return _processed_branch(nodes=[deepcopy(CONTINENT), country, site])


@dataclass
class HopCase:
    name: str
    from_kind: str
    to_kind: str
    identifier: str
    expected_from: str
    expected_to: str


HOP_CASES = [
    HopCase(
        name="child_end_holds_parent",
        from_kind=TestKind.SITE,
        to_kind=TestKind.COUNTRY,
        identifier="parent__child",
        expected_from="parent",
        expected_to="children",
    ),
    HopCase(
        name="parent_end_holds_children",
        from_kind=TestKind.COUNTRY,
        to_kind=TestKind.SITE,
        identifier="parent__child",
        expected_from="children",
        expected_to="parent",
    ),
    HopCase(
        name="generic_parent_peer_still_resolves",
        from_kind=TestKind.CONTINENT,
        to_kind=TestKind.COUNTRY,
        identifier="parent__child",
        expected_from="children",
        expected_to="parent",
    ),
    HopCase(
        name="single_declaration_identifier_keeps_both_sides",
        from_kind=TestKind.COUNTRY,
        to_kind=TestKind.SITE,
        identifier=PLAIN_IDENTIFIER,
        expected_from="managed_sites",
        expected_to="managed_by",
    ),
]


@pytest.mark.parametrize("case", HOP_CASES, ids=[case.name for case in HOP_CASES])
def test_select_hop_relationships(location_schema_branch: SchemaBranch, case: HopCase) -> None:
    from_rel, to_rel = select_hop_relationships(
        from_schema=location_schema_branch.get(name=case.from_kind, duplicate=False),
        to_schema=location_schema_branch.get(name=case.to_kind, duplicate=False),
        from_kind=case.from_kind,
        to_kind=case.to_kind,
        identifier=case.identifier,
    )

    assert from_rel is not None
    assert to_rel is not None
    assert (from_rel.name, to_rel.name) == (case.expected_from, case.expected_to)


def test_two_level_hierarchy_names_both_ends() -> None:
    # The top's parent peer and the leaf's children peer both fall back to the
    # generic; only the exact peer preference keeps the pick out of the guess.
    building = _location_variant(name="Building", parent="", children="TestingFloor")
    floor = _location_variant(name="Floor", parent="TestingBuilding", children="")
    schema_branch = _processed_branch(nodes=[building, floor])

    expectations = {
        ("TestingBuilding", "TestingFloor"): ("children", "parent"),
        ("TestingFloor", "TestingBuilding"): ("parent", "children"),
    }
    for (from_kind, to_kind), expected in expectations.items():
        from_rel, to_rel = select_hop_relationships(
            from_schema=schema_branch.get(name=from_kind, duplicate=False),
            to_schema=schema_branch.get(name=to_kind, duplicate=False),
            from_kind=from_kind,
            to_kind=to_kind,
            identifier="parent__child",
        )

        assert from_rel is not None
        assert to_rel is not None
        assert (from_rel.name, to_rel.name) == expected


@dataclass
class AmbiguousHopCase:
    name: str
    nodes: list[NodeSchema]
    hops: list[tuple[str, str]]


AMBIGUOUS_HOP_CASES = [
    AmbiguousHopCase(
        name="self_referencing_kind",
        nodes=[_location_variant(name="Area", parent="TestingArea", children="TestingArea")],
        hops=[("TestingArea", "TestingArea")],
    ),
    AmbiguousHopCase(
        name="two_kinds_under_a_loose_generic",
        nodes=[
            _location_variant(name="Area", parent=None, children=None),
            _location_variant(name="Zone", parent=None, children=None),
        ],
        hops=[("TestingArea", "TestingZone"), ("TestingZone", "TestingArea")],
    ),
    AmbiguousHopCase(
        name="self_referencing_kind_with_one_pinned_side",
        nodes=[_location_variant(name="Area", parent="TestingArea", children="")],
        hops=[("TestingArea", "TestingArea")],
    ),
    AmbiguousHopCase(
        name="two_kinds_pinning_each_other_as_children",
        nodes=[
            _location_variant(name="Building", parent=None, children="TestingFloor"),
            _location_variant(name="Floor", parent=None, children="TestingBuilding"),
        ],
        hops=[("TestingBuilding", "TestingFloor"), ("TestingFloor", "TestingBuilding")],
    ),
]


@pytest.mark.parametrize("case", AMBIGUOUS_HOP_CASES, ids=[case.name for case in AMBIGUOUS_HOP_CASES])
def test_ambiguous_hierarchy_keeps_a_deterministic_mirrored_pair(case: AmbiguousHopCase) -> None:
    # The schema cannot tell the ends apart, so the guess is the same pair in
    # every hop direction: for two distinct kinds, one direction is swapped.
    schema_branch = _processed_branch(nodes=case.nodes)

    for from_kind, to_kind in case.hops:
        from_rel, to_rel = select_hop_relationships(
            from_schema=schema_branch.get(name=from_kind, duplicate=False),
            to_schema=schema_branch.get(name=to_kind, duplicate=False),
            from_kind=from_kind,
            to_kind=to_kind,
            identifier="parent__child",
        )

        assert from_rel is not None
        assert to_rel is not None
        assert (from_rel.name, to_rel.name) == ("parent", "children")


def test_unknown_end_falls_back_to_first_declaration(location_schema_branch: SchemaBranch) -> None:
    from_rel, to_rel = select_hop_relationships(
        from_schema=location_schema_branch.get(name=TestKind.SITE, duplicate=False),
        to_schema=None,
        from_kind=TestKind.SITE,
        to_kind="TestingUnknown",
        identifier="parent__child",
    )

    assert from_rel is not None
    assert from_rel.name == "parent"
    assert to_rel is None
