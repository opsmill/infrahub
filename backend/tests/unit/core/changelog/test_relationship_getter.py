from __future__ import annotations

from infrahub.core.changelog.models import (
    NodeChangelog,
    RelationshipCardinalityManyChangelog,
    RelationshipCardinalityOneChangelog,
    RelationshipPeerChangelog,
)
from infrahub.core.changelog.relationship_getter import RelationshipChangelogGetter
from infrahub.core.constants import DiffAction


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

    merged = RelationshipChangelogGetter._merge_secondaries_by_node(secondaries)

    assert len(merged) == 2
    by_id = {changelog.node_id: changelog for changelog in merged}
    assert set(by_id) == {"peer-1", "peer-2"}
    assert set(by_id["peer-1"].relationships) == {"rel_a", "rel_b"}
    assert set(by_id["peer-2"].relationships) == {"rel_c"}


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

    merged = RelationshipChangelogGetter._merge_secondaries_by_node(secondaries)

    assert len(merged) == 1
    members = merged[0].relationships["members"]
    assert isinstance(members, RelationshipCardinalityManyChangelog)
    assert [(peer.peer_id, peer.peer_status) for peer in members.peers] == [
        ("source", DiffAction.ADDED),
        ("source", DiffAction.REMOVED),
    ]
