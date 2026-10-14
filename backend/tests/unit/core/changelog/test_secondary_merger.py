from __future__ import annotations

from infrahub.core.changelog.models import (
    NodeChangelog,
    RelationshipCardinalityManyChangelog,
    RelationshipCardinalityOneChangelog,
    RelationshipPeerChangelog,
)
from infrahub.core.changelog.secondary_merger import SecondaryChangelogMerger
from infrahub.core.constants import DiffAction, RelationshipKind


def _secondary(node_id: str, relationship_name: str) -> NodeChangelog:
    changelog = NodeChangelog(node_id=node_id, node_kind="TestPerson", display_label="label")
    changelog.relationships[relationship_name] = RelationshipCardinalityOneChangelog(
        name=relationship_name, peer_id="source"
    )
    return changelog


def test_merge_secondaries_collapses_the_same_peer_into_one_changelog() -> None:
    secondaries = [
        _secondary(node_id="peer-1", relationship_name="rel_a"),
        _secondary(node_id="peer-1", relationship_name="rel_b"),
        _secondary(node_id="peer-2", relationship_name="rel_c"),
    ]

    merged = SecondaryChangelogMerger().merge(secondaries)

    assert [changelog.node_id for changelog in merged] == ["peer-1", "peer-2"]
    assert list(merged[0].relationships) == ["rel_a", "rel_b"]
    assert list(merged[1].relationships) == ["rel_c"]
    # The first changelog seen for a peer is the one carried forward, relationships folded into it.
    assert merged[0] is secondaries[0]
    assert merged[0].relationships["rel_b"] is secondaries[1].relationships["rel_b"]


def _many_secondary(
    node_id: str, relationship_name: str, peer_id: str, status: DiffAction = DiffAction.ADDED
) -> NodeChangelog:
    changelog = NodeChangelog(node_id=node_id, node_kind="TestPerson", display_label="label")
    changelog.relationships[relationship_name] = RelationshipCardinalityManyChangelog(
        name=relationship_name,
        peers=[RelationshipPeerChangelog(peer_id=peer_id, peer_kind="TestCar", peer_status=status)],
    )
    return changelog


def test_merge_secondaries_keeps_one_entry_per_peer_and_status_for_a_shared_many_relationship_name() -> None:
    """Every peer of a secondary's many relationship is the mutated node, so only the status sets them apart."""
    secondaries = [
        _many_secondary(node_id="peer-1", relationship_name="members", peer_id="source"),
        _many_secondary(node_id="peer-1", relationship_name="members", peer_id="source"),
        _many_secondary(node_id="peer-1", relationship_name="members", peer_id="source", status=DiffAction.REMOVED),
    ]

    merged = SecondaryChangelogMerger().merge(secondaries)

    assert len(merged) == 1
    assert list(merged[0].relationships) == ["members"]
    members = merged[0].relationships["members"]
    assert isinstance(members, RelationshipCardinalityManyChangelog)
    assert [(peer.peer_id, peer.peer_status) for peer in members.peers] == [
        ("source", DiffAction.ADDED),
        ("source", DiffAction.REMOVED),
    ]


def test_merge_keeps_the_first_peer_of_a_shared_one_relationship_name() -> None:
    """A one-cardinality relationship holds a single peer, so the first secondary seen wins."""
    first = _secondary(node_id="peer-1", relationship_name="parent")
    second = _secondary(node_id="peer-1", relationship_name="parent")
    second.relationships["parent"] = RelationshipCardinalityOneChangelog(name="parent", peer_id="other-source")

    merged = SecondaryChangelogMerger().merge([first, second])

    assert len(merged) == 1
    assert list(merged[0].relationships) == ["parent"]
    assert merged[0].relationships["parent"] is first.relationships["parent"]


def test_merge_preserves_the_order_the_peers_were_built_in() -> None:
    secondaries = [
        _secondary(node_id="peer-2", relationship_name="rel_a"),
        _secondary(node_id="peer-1", relationship_name="rel_b"),
        _secondary(node_id="peer-2", relationship_name="rel_c"),
    ]

    merged = SecondaryChangelogMerger().merge(secondaries)

    assert [changelog.node_id for changelog in merged] == ["peer-2", "peer-1"]
    assert list(merged[0].relationships) == ["rel_a", "rel_c"]
    assert list(merged[1].relationships) == ["rel_b"]


def test_merge_secondaries_keeps_one_entry_when_a_merged_relationship_repeats_a_peer() -> None:
    """The entries a single folded relationship carries are deduplicated against each other too."""
    first = _many_secondary(node_id="peer-1", relationship_name="members", peer_id="source")
    second = _many_secondary(node_id="peer-1", relationship_name="members", peer_id="other")
    members = second.relationships["members"]
    assert isinstance(members, RelationshipCardinalityManyChangelog)
    members.peers.append(RelationshipPeerChangelog(peer_id="other", peer_kind="TestCar", peer_status=DiffAction.ADDED))

    merged = SecondaryChangelogMerger().merge([first, second])

    assert len(merged) == 1
    merged_members = merged[0].relationships["members"]
    assert isinstance(merged_members, RelationshipCardinalityManyChangelog)
    assert [(peer.peer_id, peer.peer_status) for peer in merged_members.peers] == [
        ("source", DiffAction.ADDED),
        ("other", DiffAction.ADDED),
    ]


def test_merge_secondaries_keeps_the_parent_of_a_later_secondary() -> None:
    """The peer's parent survives the merge whichever of its secondaries carries it."""
    without_parent = NodeChangelog(node_id="rack-1", node_kind="LocationRack", display_label="rack-1")
    without_parent.add_relationship(
        relationship_changelog=RelationshipCardinalityOneChangelog(
            name="primary_of", peer_id="site-2", peer_kind="LocationSite"
        )
    )
    with_parent = NodeChangelog(node_id="rack-1", node_kind="LocationRack", display_label="rack-1")
    parent_relationship = RelationshipCardinalityOneChangelog(name="site", peer_id="site-2", peer_kind="LocationSite")
    parent_relationship.set_parent_from_relationship(rel_kind=RelationshipKind.PARENT)
    with_parent.add_relationship(relationship_changelog=parent_relationship)

    merged = SecondaryChangelogMerger().merge([without_parent, with_parent])

    assert len(merged) == 1
    assert set(merged[0].relationships) == {"primary_of", "site"}
    assert merged[0].parent is not None
    assert merged[0].parent.node_id == "site-2"
    assert merged[0].root_node_id == "site-2"
