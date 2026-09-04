from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypedDict

import pytest

from infrahub.core.constants import RelationshipCardinality, RelationshipDirection, RelationshipKind
from infrahub.core.regeneration.derived_dependencies import (
    DerivedFieldDependencyResolver,
    PeerDependency,
)
from infrahub.core.regeneration.models import ReachedPath, RelationshipHop
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, RelationshipSchema
from infrahub.core.schema.schema_branch import SchemaBranch

if TYPE_CHECKING:
    from typing import Unpack

    from infrahub.core.schema import MainSchemaTypes


def _schema_branch(schemas: dict[str, MainSchemaTypes]) -> SchemaBranch:
    branch = SchemaBranch(cache={}, name="test")
    for kind, schema in schemas.items():
        branch.set(name=kind, schema=schema)
    return branch


def _rel(name: str, peer: str, identifier: str) -> RelationshipSchema:
    return RelationshipSchema(
        name=name,
        peer=peer,
        kind=RelationshipKind.ATTRIBUTE,
        identifier=identifier,
        cardinality=RelationshipCardinality.ONE,
        direction=RelationshipDirection.OUTBOUND,
    )


class _DerivedFields(TypedDict, total=False):
    display_label: str | None
    human_friendly_id: list[str] | None


def _node(
    name: str,
    *,
    attributes: tuple[str, ...] = ("name",),
    relationships: tuple[RelationshipSchema, ...] = (),
    **derived: Unpack[_DerivedFields],
) -> NodeSchema:
    """Build a node schema carrying an optional display_label / human_friendly_id."""
    return NodeSchema(
        name=name,
        namespace="Test",
        attributes=[AttributeSchema(name=attribute, kind="Text") for attribute in attributes],
        relationships=list(relationships),
        **derived,
    )


def _generic(name: str, *, attributes: tuple[str, ...] = ("name",), used_by: tuple[str, ...] = ()) -> GenericSchema:
    return GenericSchema(
        name=name,
        namespace="Test",
        attributes=[AttributeSchema(name=attribute, kind="Text") for attribute in attributes],
        used_by=list(used_by),
    )


# TestReader reads a derived field; the schemas below give it different compositions to resolve.
OWNER = _node("Owner", relationships=(_rel(name="parent", peer="TestGrandparent", identifier="owner__parent"),))
GRANDPARENT = _node("Grandparent")
GENERIC_MAKER = _generic("GenericMaker", used_by=("TestMakerB", "TestMakerA"))
MAKER_A = _node("MakerA")
MAKER_B = _node("MakerB")

READER_OWNER_REL = _rel(name="owner", peer="TestOwner", identifier="reader__owner")
READER_MAKER_REL = _rel(name="maker", peer="TestGenericMaker", identifier="reader__maker")

READER_OWNER_HOP = RelationshipHop(
    node_kind="TestReader",
    relationship_identifier="reader__owner",
    relationship_direction=RelationshipDirection.OUTBOUND,
)
READER_MAKER_HOP = RelationshipHop(
    node_kind="TestReader",
    relationship_identifier="reader__maker",
    relationship_direction=RelationshipDirection.OUTBOUND,
)
OWNER_PARENT_HOP = RelationshipHop(
    node_kind="TestOwner",
    relationship_identifier="owner__parent",
    relationship_direction=RelationshipDirection.OUTBOUND,
)

BASE_SCHEMAS: dict[str, MainSchemaTypes] = {
    "TestOwner": OWNER,
    "TestGrandparent": GRANDPARENT,
    "TestGenericMaker": GENERIC_MAKER,
    "TestMakerA": MAKER_A,
    "TestMakerB": MAKER_B,
}


@dataclass(frozen=True, kw_only=True)
class ResolveCase:
    name: str
    reader: NodeSchema
    readable_fields_by_kind: dict[str, set[str]]
    expected_peers: tuple[PeerDependency, ...]
    expected_widen: bool
    extra_schemas: dict[str, MainSchemaTypes] = field(default_factory=dict)


RESOLVE_CASES = [
    ResolveCase(
        name="a_plain_field_read_is_filtered_out_and_yields_no_peer",
        reader=_node("Reader"),
        readable_fields_by_kind={"TestReader": {"name"}},
        expected_peers=(),
        expected_widen=False,
    ),
    ResolveCase(
        name="own_attribute_read_yields_no_peer",
        reader=_node("Reader", attributes=("name", "color"), display_label="{{ name__value }} {{ color__value }}"),
        readable_fields_by_kind={"TestReader": {"display_label"}},
        expected_peers=(),
        expected_widen=False,
    ),
    ResolveCase(
        name="single_hop_resolves_to_the_peer_and_its_backing_field",
        reader=_node("Reader", relationships=(READER_OWNER_REL,), human_friendly_id=["owner__name__value"]),
        readable_fields_by_kind={"TestReader": {"human_friendly_id"}},
        expected_peers=(
            PeerDependency(kind="TestOwner", field_name="name", path=ReachedPath(hops=(READER_OWNER_HOP,))),
        ),
        expected_widen=False,
    ),
    ResolveCase(
        name="multi_hop_resolves_with_the_full_reversed_chain",
        reader=_node("Reader", relationships=(READER_OWNER_REL,), human_friendly_id=["owner__parent__name__value"]),
        readable_fields_by_kind={"TestReader": {"human_friendly_id"}},
        expected_peers=(
            PeerDependency(
                kind="TestGrandparent",
                field_name="name",
                path=ReachedPath(hops=(OWNER_PARENT_HOP, READER_OWNER_HOP)),
            ),
        ),
        expected_widen=False,
    ),
    ResolveCase(
        name="generic_peer_enumerates_its_implementations",
        reader=_node("Reader", relationships=(READER_MAKER_REL,), display_label="maker__name__value"),
        readable_fields_by_kind={"TestReader": {"display_label"}},
        expected_peers=(
            PeerDependency(kind="TestMakerA", field_name="name", path=ReachedPath(hops=(READER_MAKER_HOP,))),
            PeerDependency(kind="TestMakerB", field_name="name", path=ReachedPath(hops=(READER_MAKER_HOP,))),
        ),
        expected_widen=False,
    ),
    ResolveCase(
        name="unresolvable_segment_widens",
        reader=_node("Reader", relationships=(READER_OWNER_REL,), human_friendly_id=["owner__bogus__value"]),
        readable_fields_by_kind={"TestReader": {"human_friendly_id"}},
        expected_peers=(),
        expected_widen=True,
    ),
    ResolveCase(
        name="a_derived_field_with_no_declared_path_widens",
        reader=_node("Reader"),
        readable_fields_by_kind={"TestReader": {"display_label"}},
        expected_peers=(),
        expected_widen=True,
    ),
    ResolveCase(
        name="a_relationship_without_an_identifier_widens",
        reader=_node(
            "Reader",
            relationships=(
                RelationshipSchema(
                    name="owner",
                    peer="TestOwner",
                    kind=RelationshipKind.ATTRIBUTE,
                    identifier=None,
                    cardinality=RelationshipCardinality.ONE,
                    direction=RelationshipDirection.OUTBOUND,
                ),
            ),
            human_friendly_id=["owner__name__value"],
        ),
        readable_fields_by_kind={"TestReader": {"human_friendly_id"}},
        expected_peers=(),
        expected_widen=True,
    ),
    ResolveCase(
        name="a_reading_kind_absent_from_the_schema_widens",
        reader=_node("Reader"),
        readable_fields_by_kind={"TestGhost": {"display_label"}},
        expected_peers=(),
        expected_widen=True,
    ),
]


@pytest.mark.parametrize("case", RESOLVE_CASES, ids=lambda case: case.name)
def test_resolve(case: ResolveCase) -> None:
    schemas: dict[str, MainSchemaTypes] = {**BASE_SCHEMAS, "TestReader": case.reader, **case.extra_schemas}
    resolver = DerivedFieldDependencyResolver(schema_branch=_schema_branch(schemas))

    dependencies = resolver.resolve(case.readable_fields_by_kind)

    assert dependencies.peers == case.expected_peers
    assert dependencies.widen is case.expected_widen
