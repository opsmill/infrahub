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

    by_id = {changelog.node_id: changelog for changelog in merged}
    assert set(by_id) == {"peer-1", "peer-2"}
    assert set(by_id["peer-1"].relationships) == {"rel_a", "rel_b"}
    assert set(by_id["peer-2"].relationships) == {"rel_c"}


def _many_secondary(node_id: str, relationship_name: str, peer_id: str) -> NodeChangelog:
    changelog = NodeChangelog(node_id=node_id, node_kind="TestPerson", display_label="label")
    changelog.relationships[relationship_name] = RelationshipCardinalityManyChangelog(
        name=relationship_name,
        peers=[RelationshipPeerChangelog(peer_id=peer_id, peer_kind="TestCar", peer_status=DiffAction.ADDED)],
    )
    return changelog


def test_merge_secondaries_merges_peers_for_a_shared_many_relationship_name() -> None:
    secondaries = [
        _many_secondary(node_id="peer-1", relationship_name="members", peer_id="a"),
        _many_secondary(node_id="peer-1", relationship_name="members", peer_id="b"),
    ]

    merged = RelationshipChangelogGetter._merge_secondaries_by_node(secondaries)

    assert len(merged) == 1
    members = merged[0].relationships["members"]
    assert isinstance(members, RelationshipCardinalityManyChangelog)
    assert {peer.peer_id for peer in members.peers} == {"a", "b"}
