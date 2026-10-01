from __future__ import annotations

from infrahub.core.changelog.enrichment import PLACEHOLDER_LABELS, NodeLabelLoader, NodeLabels
from infrahub.core.changelog.models import (
    NodeChangelog,
    RelationshipCardinalityManyChangelog,
    RelationshipCardinalityOneChangelog,
    RelationshipPeerChangelog,
)
from infrahub.core.changelog.peer_labels import PeerLabelResolver, ResolvedPeerLabels
from infrahub.core.constants import DiffAction


class _StubLabelReader:
    """Serves the labels it was given, standing in for the reader that queries the graph."""

    def __init__(self, labels: dict[str, NodeLabels]) -> None:
        self.labels = labels

    async def load_labels(self, node_ids: list[str]) -> dict[str, NodeLabels]:
        return {node_id: self.labels[node_id] for node_id in node_ids if node_id in self.labels}

    async def load_hfids(self, node_ids: list[str]) -> dict[str, list[str] | None]:
        return {node_id: self.labels[node_id].hfid for node_id in node_ids if node_id in self.labels}


def _label_loader(labels: dict[str, NodeLabels]) -> NodeLabelLoader:
    return NodeLabelLoader(reader=_StubLabelReader(labels))


def _changelog_with_both_cardinalities() -> NodeChangelog:
    changelog = NodeChangelog(node_id="source", node_kind="TestPerson", display_label="label")
    changelog.relationships["owner"] = RelationshipCardinalityOneChangelog(
        name="owner", peer_id="current", peer_id_previous="previous"
    )
    changelog.relationships["cars"] = RelationshipCardinalityManyChangelog(
        name="cars",
        peers=[RelationshipPeerChangelog(peer_id="car-1", peer_kind="TestCar", peer_status=DiffAction.ADDED)],
    )
    return changelog


def test_referenced_peer_ids_covers_current_previous_and_many_peers() -> None:
    resolver = PeerLabelResolver(label_loader=_label_loader({}))

    ids = resolver.referenced_peer_ids(changelog=_changelog_with_both_cardinalities())

    assert ids == {"current", "previous", "car-1"}


async def test_resolve_reports_what_was_referenced_and_what_was_resolved() -> None:
    resolver = PeerLabelResolver(
        label_loader=_label_loader({"current": NodeLabels(display_label="Current", hfid=["current"])})
    )

    peer_labels = await resolver.resolve(changelog=_changelog_with_both_cardinalities())

    assert peer_labels.referenced_count == 3
    assert peer_labels.resolved_count == 1
    assert peer_labels.labels_of(peer_id="current") == NodeLabels(display_label="Current", hfid=["current"])
    assert peer_labels.labels_of(peer_id="previous") is PLACEHOLDER_LABELS
    assert peer_labels.labels_of(peer_id="car-1") is PLACEHOLDER_LABELS


def test_enrich_fills_resolved_peers_and_leaves_the_others_unset() -> None:
    changelog = _changelog_with_both_cardinalities()
    peer_labels = ResolvedPeerLabels(
        labels={"current": NodeLabels(display_label="Current", hfid=["current"])}, referenced_count=3
    )

    peer_labels.enrich(changelog=changelog)

    assert {
        peer.peer_id: (peer.peer_display_label, peer.peer_hfid)
        for relationship in changelog.relationships.values()
        for peer in relationship.peer_entries()
    } == {"current": ("Current", ["current"]), "car-1": (None, None)}
    owner = changelog.relationships["owner"]
    assert isinstance(owner, RelationshipCardinalityOneChangelog)
    assert (owner.peer_id, owner.peer_id_previous) == ("current", "previous")


def test_labels_of_falls_back_to_the_placeholder_for_an_unresolved_peer() -> None:
    peer_labels = ResolvedPeerLabels(labels={}, referenced_count=1)

    labels = peer_labels.labels_of(peer_id="gone")

    assert labels is PLACEHOLDER_LABELS


async def test_a_peer_referenced_twice_is_counted_and_resolved_once() -> None:
    changelog = NodeChangelog(node_id="source", node_kind="TestPerson", display_label="label")
    changelog.relationships["owner"] = RelationshipCardinalityOneChangelog(name="owner", peer_id="shared")
    changelog.relationships["previous_owner"] = RelationshipCardinalityOneChangelog(
        name="previous_owner", peer_id_previous="shared"
    )
    changelog.relationships["driver"] = RelationshipCardinalityOneChangelog(name="driver")
    resolver = PeerLabelResolver(label_loader=_label_loader({"shared": NodeLabels(display_label="Shared", hfid=None)}))

    ids = resolver.referenced_peer_ids(changelog=changelog)
    peer_labels = await resolver.resolve(changelog=changelog)

    assert ids == {"shared"}
    assert peer_labels.referenced_count == 1
    assert peer_labels.resolved_count == 1
