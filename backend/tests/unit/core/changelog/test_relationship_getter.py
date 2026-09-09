from __future__ import annotations

from infrahub.core.changelog.models import NodeChangelog, RelationshipCardinalityOneChangelog
from infrahub.core.changelog.relationship_getter import RelationshipChangelogGetter


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
