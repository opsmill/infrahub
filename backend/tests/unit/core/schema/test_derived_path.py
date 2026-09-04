from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import RelationshipCardinality, RelationshipDirection, RelationshipKind
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, RelationshipSchema
from infrahub.core.schema.derived_path import (
    DerivedPathHop,
    DerivedPathResolution,
    DerivedPathResolver,
    ReachesPeer,
    ScopedToReadingKind,
    Unresolvable,
)
from infrahub.core.schema.schema_branch import SchemaBranch

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes


def _rel(name: str, peer: str, identifier: str | None) -> RelationshipSchema:
    return RelationshipSchema(
        name=name,
        peer=peer,
        kind=RelationshipKind.ATTRIBUTE,
        identifier=identifier,
        cardinality=RelationshipCardinality.ONE,
        direction=RelationshipDirection.OUTBOUND,
    )


def _node(
    name: str, *, attributes: tuple[str, ...] = ("name",), relationships: tuple[RelationshipSchema, ...] = ()
) -> NodeSchema:
    return NodeSchema(
        name=name,
        namespace="Test",
        attributes=[AttributeSchema(name=attribute, kind="Text") for attribute in attributes],
        relationships=list(relationships),
    )


def _generic(name: str, *, used_by: tuple[str, ...]) -> GenericSchema:
    return GenericSchema(
        name=name,
        namespace="Test",
        attributes=[AttributeSchema(name="name", kind="Text")],
        used_by=list(used_by),
    )


def _branch(schemas: dict[str, MainSchemaTypes]) -> SchemaBranch:
    branch = SchemaBranch(cache={}, name="test")
    for kind, schema in schemas.items():
        branch.set(name=kind, schema=schema)
    return branch


READER_OWNER_REL = _rel(name="owner", peer="TestOwner", identifier="reader__owner")
READER_MAKER_REL = _rel(name="maker", peer="TestGenericMaker", identifier="reader__maker")
READER_GHOST_REL = _rel(name="ghost", peer="TestMissing", identifier="reader__ghost")
OWNER = _node("Owner", relationships=(_rel(name="parent", peer="TestGrandparent", identifier="owner__parent"),))
GRANDPARENT = _node("Grandparent")
GENERIC_MAKER = _generic("GenericMaker", used_by=("TestMakerB", "TestMakerA"))

BASE_SCHEMAS: dict[str, MainSchemaTypes] = {
    "TestOwner": OWNER,
    "TestGrandparent": GRANDPARENT,
    "TestGenericMaker": GENERIC_MAKER,
    "TestMakerA": _node("MakerA"),
    "TestMakerB": _node("MakerB"),
}

READER_OWNER_HOP = DerivedPathHop(
    owner_kind="TestReader",
    relationship_identifier="reader__owner",
    relationship_direction=RelationshipDirection.OUTBOUND,
)
READER_MAKER_HOP = DerivedPathHop(
    owner_kind="TestReader",
    relationship_identifier="reader__maker",
    relationship_direction=RelationshipDirection.OUTBOUND,
)
OWNER_PARENT_HOP = DerivedPathHop(
    owner_kind="TestOwner",
    relationship_identifier="owner__parent",
    relationship_direction=RelationshipDirection.OUTBOUND,
)


@dataclass(frozen=True, kw_only=True)
class Case:
    name: str
    reader: NodeSchema
    path: str
    expected: DerivedPathResolution


CASES = [
    Case(
        name="own_attribute_at_root_is_scoped",
        reader=_node("Reader", attributes=("name", "color")),
        path="color__value",
        expected=ScopedToReadingKind(),
    ),
    Case(
        name="single_hop_reaches_the_peer_with_the_hop_in_walk_order",
        reader=_node("Reader", relationships=(READER_OWNER_REL,)),
        path="owner__name__value",
        expected=ReachesPeer(backing_field="name", peer_kinds=("TestOwner",), hops=(READER_OWNER_HOP,)),
    ),
    Case(
        name="multi_hop_reaches_the_far_peer_with_every_hop_in_walk_order",
        reader=_node("Reader", relationships=(READER_OWNER_REL,)),
        path="owner__parent__name__value",
        expected=ReachesPeer(
            backing_field="name", peer_kinds=("TestGrandparent",), hops=(READER_OWNER_HOP, OWNER_PARENT_HOP)
        ),
    ),
    Case(
        name="a_generic_peer_enumerates_its_sorted_implementations",
        reader=_node("Reader", relationships=(READER_MAKER_REL,)),
        path="maker__name__value",
        expected=ReachesPeer(backing_field="name", peer_kinds=("TestMakerA", "TestMakerB"), hops=(READER_MAKER_HOP,)),
    ),
    Case(
        name="an_unknown_segment_is_unresolvable",
        reader=_node("Reader", relationships=(READER_OWNER_REL,)),
        path="owner__bogus__value",
        expected=Unresolvable(),
    ),
    Case(
        name="a_relationship_without_an_identifier_is_unresolvable",
        reader=_node("Reader", relationships=(_rel(name="owner", peer="TestOwner", identifier=None),)),
        path="owner__name__value",
        expected=Unresolvable(),
    ),
    Case(
        name="a_path_ending_on_a_relationship_is_unresolvable",
        reader=_node("Reader", relationships=(READER_OWNER_REL,)),
        path="owner",
        expected=Unresolvable(),
    ),
    Case(
        name="a_relationship_onto_a_kind_absent_from_the_branch_is_unresolvable",
        reader=_node("Reader", relationships=(READER_GHOST_REL,)),
        path="ghost__name__value",
        expected=Unresolvable(),
    ),
]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_resolve(case: Case) -> None:
    resolver = DerivedPathResolver(schema_branch=_branch({**BASE_SCHEMAS, "TestReader": case.reader}))

    resolution = resolver.resolve(reading_schema=case.reader, path=case.path)

    assert resolution == case.expected
