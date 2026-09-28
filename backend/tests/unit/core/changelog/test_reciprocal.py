from dataclasses import dataclass

import pytest

from infrahub.core.changelog.models import (
    ChangelogRelatedNode,
    NodeChangelog,
    RelationshipCardinalityManyChangelog,
    RelationshipCardinalityOneChangelog,
)
from infrahub.core.changelog.reciprocal import ReciprocalRelationshipBuilder
from infrahub.core.constants import DiffAction, RelationshipCardinality, RelationshipDirection, RelationshipKind
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

    assert list(relationships) == ["parent"]
    assert relationships["parent"].model_dump() == {
        "name": "parent",
        "cardinality": "one",
        "peer_id": "source",
        "peer_kind": "LocRack",
        "peer_display_label": "rack-1",
        "peer_hfid": ["rack-1"],
        "peer_id_previous": None,
        "peer_kind_previous": None,
        "peer_status": DiffAction.ADDED,
        "properties": {},
    }


def test_build_reports_the_primary_as_the_previous_peer_of_a_one_cardinality_reciprocal() -> None:
    relationships = ReciprocalRelationshipBuilder().build(
        peer_schema=HIERARCHY_PEER_SCHEMA,
        rel_schema=PARENT_SIDE_RELATIONSHIP,
        primary_changelog=PRIMARY_CHANGELOG,
        peer_status=DiffAction.REMOVED,
    )

    assert list(relationships) == ["parent"]
    assert relationships["parent"].model_dump() == {
        "name": "parent",
        "cardinality": "one",
        "peer_id": None,
        "peer_kind": None,
        "peer_display_label": None,
        "peer_hfid": None,
        "peer_id_previous": "source",
        "peer_kind_previous": "LocRack",
        "peer_status": DiffAction.REMOVED,
        "properties": {},
    }


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

    assert list(relationships) == ["children"]
    assert relationships["children"].model_dump() == {
        "name": "children",
        "cardinality": "many",
        "peers": [
            {
                "peer_id": "source",
                "peer_kind": "LocRack",
                "peer_display_label": "rack-1",
                "peer_hfid": ["rack-1"],
                "peer_status": peer_status,
                "properties": {},
            }
        ],
    }


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

    assert list(relationships) == ["parent", "children"]
    parent = relationships["parent"]
    assert isinstance(parent, RelationshipCardinalityOneChangelog)
    assert (parent.peer_id, parent.peer_kind, parent.peer_status) == ("source", "LocRack", DiffAction.ADDED)
    children = relationships["children"]
    assert isinstance(children, RelationshipCardinalityManyChangelog)
    assert [(peer.peer_id, peer.peer_status) for peer in children.peers] == [("source", DiffAction.ADDED)]


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


PARENT_PEER_SCHEMA = NodeSchema(
    name="Rack",
    namespace="Loc",
    relationships=[
        RelationshipSchema(
            name="site",
            peer="LocSite",
            identifier="site__rack",
            kind=RelationshipKind.PARENT,
            cardinality=RelationshipCardinality.ONE,
            direction=RelationshipDirection.OUTBOUND,
        ),
    ],
)

RACK_SIDE_RELATIONSHIP = RelationshipSchema(
    name="racks",
    peer="LocRack",
    identifier="site__rack",
    cardinality=RelationshipCardinality.MANY,
    direction=RelationshipDirection.INBOUND,
)


@pytest.mark.parametrize("peer_status", [DiffAction.ADDED, DiffAction.REMOVED])
def test_build_names_the_primary_as_the_parent_of_a_parent_reciprocal(peer_status: DiffAction) -> None:
    """A removed parent is still the parent the peer-side changelog names."""
    relationships = ReciprocalRelationshipBuilder().build(
        peer_schema=PARENT_PEER_SCHEMA,
        rel_schema=RACK_SIDE_RELATIONSHIP,
        primary_changelog=PRIMARY_CHANGELOG,
        peer_status=peer_status,
    )

    site = relationships["site"]
    assert isinstance(site, RelationshipCardinalityOneChangelog)
    assert site.parent == ChangelogRelatedNode(node_id="source", node_kind="LocRack")


def test_build_leaves_a_generic_reciprocal_without_a_parent() -> None:
    relationships = ReciprocalRelationshipBuilder().build(
        peer_schema=HIERARCHY_PEER_SCHEMA,
        rel_schema=PARENT_SIDE_RELATIONSHIP,
        primary_changelog=PRIMARY_CHANGELOG,
        peer_status=DiffAction.ADDED,
    )

    parent = relationships["parent"]
    assert isinstance(parent, RelationshipCardinalityOneChangelog)
    assert parent.parent is None
