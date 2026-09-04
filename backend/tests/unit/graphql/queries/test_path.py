from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

import pytest

from infrahub.core.schema import RelationshipSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.graphql.queries.path import select_hop_relationships
from tests.constants import TestKind
from tests.helpers.schema import CONTINENT, COUNTRY, LOCATION, SITE

PLAIN_IDENTIFIER = "country__managed_site"


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
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(
        schema=SchemaRoot(generics=[deepcopy(LOCATION)], nodes=[deepcopy(CONTINENT), country, site])
    )
    schema_branch.process()
    return schema_branch


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


def test_loose_hierarchy_keeps_a_deterministic_mirrored_pair() -> None:
    # Both kinds leave parent/children unset, so both peers default to the
    # hierarchy generic and both ends keep both candidates: the schema cannot
    # tell the ends apart. The guess is the same pair in both hop directions,
    # so one direction names the ends swapped — known limit until hops carry
    # the edge orientation.
    area = deepcopy(CONTINENT)
    area.name = "Area"
    area.parent = None
    area.children = None
    zone = deepcopy(CONTINENT)
    zone.name = "Zone"
    zone.parent = None
    zone.children = None
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(generics=[deepcopy(LOCATION)], nodes=[area, zone]))
    schema_branch.process()

    for from_kind, to_kind in (("TestingArea", "TestingZone"), ("TestingZone", "TestingArea")):
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


def test_self_referencing_hierarchy_reports_a_mirrored_pair() -> None:
    # Both ends declare both sides with self peers: the schema cannot tell the
    # ends apart, but the answer must stay one edge (a parent side and a
    # children side), picked deterministically.
    area = deepcopy(CONTINENT)
    area.name = "Area"
    area.parent = "TestingArea"
    area.children = "TestingArea"
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=SchemaRoot(generics=[deepcopy(LOCATION)], nodes=[area]))
    schema_branch.process()

    from_rel, to_rel = select_hop_relationships(
        from_schema=schema_branch.get(name="TestingArea", duplicate=False),
        to_schema=schema_branch.get(name="TestingArea", duplicate=False),
        from_kind="TestingArea",
        to_kind="TestingArea",
        identifier="parent__child",
    )

    assert from_rel is not None
    assert to_rel is not None
    assert (from_rel.name, to_rel.name) == ("parent", "children")
