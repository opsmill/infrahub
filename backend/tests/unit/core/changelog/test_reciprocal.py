from dataclasses import dataclass

import pytest

from infrahub.core.changelog.models import (
    NodeChangelog,
    RelationshipCardinalityManyChangelog,
    RelationshipCardinalityOneChangelog,
)
from infrahub.core.changelog.reciprocal import ReciprocalRelationshipBuilder
from infrahub.core.constants import DiffAction, RelationshipCardinality, RelationshipDirection
from infrahub.core.constants.schema import PARENT_CHILD_IDENTIFIER
from infrahub.core.schema import NodeSchema, RelationshipSchema

HIERARCHY_PEER_SCHEMA = NodeSchema(
    name="Site",
    namespace="Loc",
    relationships=[
        RelationshipSchema(
            name="parent",
            peer="LocRegion",
            identifier=PARENT_CHILD_IDENTIFIER,
            cardinality=RelationshipCardinality.ONE,
            direction=RelationshipDirection.OUTBOUND,
        ),
        RelationshipSchema(
            name="children",
            peer="LocRack",
            identifier=PARENT_CHILD_IDENTIFIER,
            cardinality=RelationshipCardinality.MANY,
            direction=RelationshipDirection.INBOUND,
        ),
    ],
)

# A node that inherits a hierarchy but declares its own `children` under another identifier keeps
# only `parent` under `parent__child`, because the generated `children` is then skipped. Schema
# validation accepts it.
ONE_SIDED_PEER_SCHEMA = NodeSchema(
    name="Room",
    namespace="Loc",
    relationships=[
        RelationshipSchema(
            name="parent",
            peer="LocSite",
            identifier=PARENT_CHILD_IDENTIFIER,
            cardinality=RelationshipCardinality.ONE,
            direction=RelationshipDirection.OUTBOUND,
        ),
    ],
)


@dataclass
class PeerRelationshipCase:
    name: str
    peer: NodeSchema
    local: RelationshipSchema
    expected_names: list[str]


PEER_RELATIONSHIP_CASES: list[PeerRelationshipCase] = [
    PeerRelationshipCase(
        name="the_child_side_resolves_to_children",
        peer=HIERARCHY_PEER_SCHEMA,
        local=RelationshipSchema(
            name="parent",
            peer="LocSite",
            identifier=PARENT_CHILD_IDENTIFIER,
            cardinality=RelationshipCardinality.ONE,
            direction=RelationshipDirection.OUTBOUND,
        ),
        expected_names=["children"],
    ),
    PeerRelationshipCase(
        name="the_parent_side_resolves_to_parent",
        peer=HIERARCHY_PEER_SCHEMA,
        local=RelationshipSchema(
            name="children",
            peer="LocSite",
            identifier=PARENT_CHILD_IDENTIFIER,
            cardinality=RelationshipCardinality.MANY,
            direction=RelationshipDirection.INBOUND,
        ),
        expected_names=["parent"],
    ),
    PeerRelationshipCase(
        # Schema validation only checks the peers the pair declares, so it never sees a third kind.
        name="a_third_kind_reusing_the_identifier_gets_every_candidate",
        peer=HIERARCHY_PEER_SCHEMA,
        local=RelationshipSchema(
            name="site",
            peer="LocSite",
            identifier=PARENT_CHILD_IDENTIFIER,
            cardinality=RelationshipCardinality.ONE,
            direction=RelationshipDirection.BIDIR,
        ),
        expected_names=["parent", "children"],
    ),
    PeerRelationshipCase(
        # Nothing mirrors an outbound side on a peer that only declares one. Report it anyway,
        # so a change that did happen is never dropped.
        name="a_lone_candidate_is_reported_even_when_it_does_not_mirror",
        peer=ONE_SIDED_PEER_SCHEMA,
        local=RelationshipSchema(
            name="parent",
            peer="LocRoom",
            identifier=PARENT_CHILD_IDENTIFIER,
            cardinality=RelationshipCardinality.ONE,
            direction=RelationshipDirection.OUTBOUND,
        ),
        expected_names=["parent"],
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in PEER_RELATIONSHIP_CASES])
def test_peer_relationships(test_case: PeerRelationshipCase) -> None:
    """A hierarchy resolves by direction. When nothing mirrors it, every candidate is reported."""
    resolved = ReciprocalRelationshipBuilder().peer_relationships(
        peer_schema=test_case.peer, rel_schema=test_case.local
    )

    assert [relationship.name for relationship in resolved] == test_case.expected_names


PRIMARY_CHANGELOG = NodeChangelog(node_id="source", node_kind="LocRack", display_label="rack-1", hfid=["rack-1"])

CHILD_SIDE_RELATIONSHIP = RelationshipSchema(
    name="parent",
    peer="LocSite",
    identifier=PARENT_CHILD_IDENTIFIER,
    cardinality=RelationshipCardinality.ONE,
    direction=RelationshipDirection.OUTBOUND,
)
PARENT_SIDE_RELATIONSHIP = RelationshipSchema(
    name="children",
    peer="LocSite",
    identifier=PARENT_CHILD_IDENTIFIER,
    cardinality=RelationshipCardinality.MANY,
    direction=RelationshipDirection.INBOUND,
)


def test_build_reports_the_primary_as_the_added_peer_of_a_one_cardinality_reciprocal() -> None:
    relationships = ReciprocalRelationshipBuilder().build(
        peer_schema=HIERARCHY_PEER_SCHEMA,
        rel_schema=PARENT_SIDE_RELATIONSHIP,
        primary_changelog=PRIMARY_CHANGELOG,
        peer_status=DiffAction.ADDED,
    )

    parent = relationships["parent"]
    assert isinstance(parent, RelationshipCardinalityOneChangelog)
    assert parent.peer_id == PRIMARY_CHANGELOG.node_id
    assert parent.peer_kind == PRIMARY_CHANGELOG.node_kind
    assert parent.peer_display_label == PRIMARY_CHANGELOG.display_label
    assert parent.peer_hfid == PRIMARY_CHANGELOG.hfid
    assert parent.peer_status == DiffAction.ADDED


def test_build_reports_the_primary_as_the_previous_peer_of_a_one_cardinality_reciprocal() -> None:
    relationships = ReciprocalRelationshipBuilder().build(
        peer_schema=HIERARCHY_PEER_SCHEMA,
        rel_schema=PARENT_SIDE_RELATIONSHIP,
        primary_changelog=PRIMARY_CHANGELOG,
        peer_status=DiffAction.REMOVED,
    )

    parent = relationships["parent"]
    assert isinstance(parent, RelationshipCardinalityOneChangelog)
    assert parent.peer_id_previous == PRIMARY_CHANGELOG.node_id
    assert parent.peer_kind_previous == PRIMARY_CHANGELOG.node_kind
    assert parent.peer_id is None
    assert parent.peer_display_label is None
    assert parent.peer_hfid is None
    assert parent.peer_status == DiffAction.REMOVED


@pytest.mark.parametrize("peer_status", [DiffAction.ADDED, DiffAction.REMOVED])
def test_build_carries_the_status_on_the_single_peer_of_a_many_cardinality_reciprocal(
    peer_status: DiffAction,
) -> None:
    relationships = ReciprocalRelationshipBuilder().build(
        peer_schema=HIERARCHY_PEER_SCHEMA,
        rel_schema=CHILD_SIDE_RELATIONSHIP,
        primary_changelog=PRIMARY_CHANGELOG,
        peer_status=peer_status,
    )

    children = relationships["children"]
    assert isinstance(children, RelationshipCardinalityManyChangelog)
    assert len(children.peers) == 1
    peer = children.peers[0]
    assert peer.peer_id == PRIMARY_CHANGELOG.node_id
    assert peer.peer_kind == PRIMARY_CHANGELOG.node_kind
    assert peer.peer_display_label == PRIMARY_CHANGELOG.display_label
    assert peer.peer_hfid == PRIMARY_CHANGELOG.hfid
    assert peer.peer_status == peer_status


def test_build_mirrors_every_candidate_when_none_matches_the_direction() -> None:
    """A bidirectional relationship mirrors nothing, so both sides of the hierarchy are reported."""
    relationships = ReciprocalRelationshipBuilder().build(
        peer_schema=HIERARCHY_PEER_SCHEMA,
        rel_schema=RelationshipSchema(
            name="siblings",
            peer="LocSite",
            identifier=PARENT_CHILD_IDENTIFIER,
            cardinality=RelationshipCardinality.MANY,
            direction=RelationshipDirection.BIDIR,
        ),
        primary_changelog=PRIMARY_CHANGELOG,
        peer_status=DiffAction.ADDED,
    )

    assert isinstance(relationships["parent"], RelationshipCardinalityOneChangelog)
    assert isinstance(relationships["children"], RelationshipCardinalityManyChangelog)


def test_build_returns_nothing_when_the_peer_declares_no_side_of_the_relationship() -> None:
    relationships = ReciprocalRelationshipBuilder().build(
        peer_schema=HIERARCHY_PEER_SCHEMA,
        rel_schema=RelationshipSchema(
            name="owner",
            peer="LocSite",
            identifier="rack__owner",
            cardinality=RelationshipCardinality.ONE,
            direction=RelationshipDirection.OUTBOUND,
        ),
        primary_changelog=PRIMARY_CHANGELOG,
        peer_status=DiffAction.ADDED,
    )

    assert relationships == {}
