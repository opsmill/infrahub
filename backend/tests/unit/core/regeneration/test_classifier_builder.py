from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from infrahub.core.constants import RelationshipCardinality, RelationshipDirection, RelationshipKind
from infrahub.core.regeneration.classifier_builder import QueryClassifierBuilder
from infrahub.core.regeneration.derived_dependencies import DerivedFieldDependencies, PeerDependency
from infrahub.core.regeneration.impact_classifier import QueryImpactClassifier
from infrahub.core.regeneration.models import ReachedPath, RelationshipHop
from infrahub.core.schema import AttributeSchema, MainSchemaTypes, NodeSchema, RelationshipSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.graphql.analyzer import ObjectAccess

QUERY_BRANCH = "test/builder"


@dataclass
class _FakeQuery:
    requested_read: dict[str, ObjectAccess]
    only_has_unique_targets: bool = True
    traversed_kinds: set[str] = field(default_factory=set)
    relationship_reached_paths_by_kind: dict[str, tuple[ReachedPath, ...]] = field(default_factory=dict)


def _node(
    name: str,
    *,
    relationships: tuple[RelationshipSchema, ...] = (),
    human_friendly_id: list[str] | None = None,
) -> NodeSchema:
    return NodeSchema(
        name=name,
        namespace="Test",
        attributes=[AttributeSchema(name="name", kind="Text")],
        relationships=list(relationships),
        human_friendly_id=human_friendly_id,
    )


READER = _node(
    "Reader",
    relationships=(
        RelationshipSchema(
            name="owner",
            peer="TestOwner",
            kind=RelationshipKind.ATTRIBUTE,
            identifier="reader__owner",
            cardinality=RelationshipCardinality.ONE,
            direction=RelationshipDirection.OUTBOUND,
        ),
    ),
    human_friendly_id=["owner__name__value"],
)
OWNER = _node("Owner")
OWNER_HOP = RelationshipHop(
    node_kind="TestReader",
    relationship_identifier="reader__owner",
    relationship_direction=RelationshipDirection.OUTBOUND,
)


def _builder() -> QueryClassifierBuilder:
    schemas: dict[str, MainSchemaTypes] = {"TestReader": READER, "TestOwner": OWNER}
    branch = SchemaBranch(cache={}, name="test")
    for kind, schema in schemas.items():
        branch.set(name=kind, schema=schema)
    return QueryClassifierBuilder(query_branch=QUERY_BRANCH, schema_branch=branch)


def test_build_folds_a_derived_peer_into_the_classifier() -> None:
    report = _FakeQuery(requested_read={"TestReader": ObjectAccess(attributes={"human_friendly_id"})})

    classifier = _builder().build(report)

    assert classifier == QueryImpactClassifier(
        query_branch=QUERY_BRANCH,
        only_has_unique_targets=True,
        traversed_kinds={"TestOwner"},
        readable_fields_by_kind={"TestReader": {"human_friendly_id"}, "TestOwner": {"name"}},
        reached_paths_by_kind={"TestOwner": (ReachedPath(hops=(OWNER_HOP,)),)},
        depends_on_everything=False,
    )


def test_build_passes_a_plain_read_through_unchanged() -> None:
    report = _FakeQuery(
        requested_read={"TestReader": ObjectAccess(attributes={"name"})},
        only_has_unique_targets=False,
    )

    classifier = _builder().build(report)

    assert classifier == QueryImpactClassifier(
        query_branch=QUERY_BRANCH,
        only_has_unique_targets=False,
        traversed_kinds=set(),
        readable_fields_by_kind={"TestReader": {"name"}},
        reached_paths_by_kind={},
        depends_on_everything=False,
    )


MAKER_HOP = RelationshipHop(
    node_kind="TestReader",
    relationship_identifier="reader__maker",
    relationship_direction=RelationshipDirection.OUTBOUND,
)
OWNER_PEER = PeerDependency(kind="TestOwner", field_name="name", path=ReachedPath(hops=(OWNER_HOP,)))
QUERY_PATH = ReachedPath(hops=(MAKER_HOP,))


def _classifier(
    *,
    traversed_kinds: set[str],
    readable_fields_by_kind: dict[str, set[str]],
    reached_paths_by_kind: dict[str, tuple[ReachedPath, ...]],
    depends_on_everything: bool,
) -> QueryImpactClassifier:
    """A classifier over the fold cases' fixed branch and unique-target context."""
    return QueryImpactClassifier(
        query_branch=QUERY_BRANCH,
        only_has_unique_targets=True,
        traversed_kinds=traversed_kinds,
        readable_fields_by_kind=readable_fields_by_kind,
        reached_paths_by_kind=reached_paths_by_kind,
        depends_on_everything=depends_on_everything,
    )


@dataclass(frozen=True, kw_only=True)
class FoldCase:
    name: str
    readable_fields_by_kind: dict[str, set[str]]
    traversed_kinds: set[str]
    reached_paths_by_kind: dict[str, tuple[ReachedPath, ...]]
    dependencies: DerivedFieldDependencies
    expected: QueryImpactClassifier


FOLD_CASES = [
    FoldCase(
        name="a_peer_the_query_does_not_read_becomes_a_narrowable_traversed_kind",
        readable_fields_by_kind={"TestReader": {"human_friendly_id"}},
        traversed_kinds=set(),
        reached_paths_by_kind={},
        dependencies=DerivedFieldDependencies(peers=(OWNER_PEER,), widen=False),
        expected=_classifier(
            traversed_kinds={"TestOwner"},
            readable_fields_by_kind={"TestReader": {"human_friendly_id"}, "TestOwner": {"name"}},
            reached_paths_by_kind={"TestOwner": (ReachedPath(hops=(OWNER_HOP,)),)},
            depends_on_everything=False,
        ),
    ),
    FoldCase(
        name="a_peer_already_read_at_a_root_widens",
        readable_fields_by_kind={"TestReader": {"human_friendly_id"}, "TestOwner": {"name"}},
        traversed_kinds=set(),
        reached_paths_by_kind={},
        dependencies=DerivedFieldDependencies(peers=(OWNER_PEER,), widen=False),
        expected=_classifier(
            traversed_kinds=set(),
            readable_fields_by_kind={"TestReader": {"human_friendly_id"}, "TestOwner": {"name"}},
            reached_paths_by_kind={},
            depends_on_everything=True,
        ),
    ),
    FoldCase(
        name="a_peer_already_traversed_with_a_path_unions_the_derived_path",
        readable_fields_by_kind={"TestReader": {"human_friendly_id"}, "TestOwner": {"description"}},
        traversed_kinds={"TestOwner"},
        reached_paths_by_kind={"TestOwner": (QUERY_PATH,)},
        dependencies=DerivedFieldDependencies(peers=(OWNER_PEER,), widen=False),
        expected=_classifier(
            traversed_kinds={"TestOwner"},
            readable_fields_by_kind={"TestReader": {"human_friendly_id"}, "TestOwner": {"description", "name"}},
            reached_paths_by_kind={"TestOwner": (QUERY_PATH, ReachedPath(hops=(OWNER_HOP,)))},
            depends_on_everything=False,
        ),
    ),
    FoldCase(
        name="a_peer_traversed_without_a_resolvable_path_widens",
        readable_fields_by_kind={"TestReader": {"human_friendly_id"}, "TestOwner": {"description"}},
        traversed_kinds={"TestOwner"},
        reached_paths_by_kind={},
        dependencies=DerivedFieldDependencies(peers=(OWNER_PEER,), widen=False),
        expected=_classifier(
            traversed_kinds={"TestOwner"},
            readable_fields_by_kind={"TestReader": {"human_friendly_id"}, "TestOwner": {"description"}},
            reached_paths_by_kind={},
            depends_on_everything=True,
        ),
    ),
    FoldCase(
        name="an_unresolved_derived_read_propagates_widen",
        readable_fields_by_kind={"TestReader": {"human_friendly_id"}},
        traversed_kinds=set(),
        reached_paths_by_kind={},
        dependencies=DerivedFieldDependencies(peers=(), widen=True),
        expected=_classifier(
            traversed_kinds=set(),
            readable_fields_by_kind={"TestReader": {"human_friendly_id"}},
            reached_paths_by_kind={},
            depends_on_everything=True,
        ),
    ),
]


@pytest.mark.parametrize("case", FOLD_CASES, ids=lambda case: case.name)
def test_build_query_classifier(case: FoldCase) -> None:
    result = _builder().build_query_classifier(
        only_has_unique_targets=True,
        readable_fields_by_kind=case.readable_fields_by_kind,
        traversed_kinds=case.traversed_kinds,
        reached_paths_by_kind=case.reached_paths_by_kind,
        dependencies=case.dependencies,
    )

    assert result == case.expected
