from __future__ import annotations

from typing import TYPE_CHECKING

from .enrichment import PLACEHOLDER_LABELS
from .models import RelationshipCardinalityManyChangelog, RelationshipCardinalityOneChangelog

if TYPE_CHECKING:
    from .enrichment import NodeLabelLoader, NodeLabels
    from .models import NodeChangelog


class ResolvedPeerLabels:
    """The labels of the peers one changelog references, resolved in a single load."""

    def __init__(self, labels: dict[str, NodeLabels], referenced_count: int) -> None:
        self._labels = labels
        self._referenced_count = referenced_count

    @property
    def referenced_count(self) -> int:
        """How many distinct peers were asked for."""
        return self._referenced_count

    @property
    def resolved_count(self) -> int:
        """How many distinct peers were resolved."""
        return len(self._labels)

    def labels_of(self, peer_id: str) -> NodeLabels:
        """Return a peer's labels, or a placeholder when it could not be resolved (e.g. deleted)."""
        return self._labels.get(peer_id, PLACEHOLDER_LABELS)

    def enrich(self, changelog: NodeChangelog) -> None:
        """Fill each relationship peer of a changelog with its display label and HFID.

        A peer that could not be resolved keeps both unset.
        """
        for relationship in changelog.relationships.values():
            for peer in relationship.peer_entries():
                peer_labels = self._labels.get(peer.peer_id) if peer.peer_id else None
                if peer_labels is None:
                    continue
                peer.peer_display_label = peer_labels.display_label
                peer.peer_hfid = peer_labels.hfid


class PeerLabelResolver:
    """Resolves the labels of every peer a changelog's relationships reference, in one batched load."""

    def __init__(self, label_loader: NodeLabelLoader) -> None:
        self._label_loader = label_loader

    async def resolve(self, changelog: NodeChangelog) -> ResolvedPeerLabels:
        referenced_peer_ids = self.referenced_peer_ids(changelog=changelog)
        labels = await self._label_loader.load_labels(referenced_peer_ids)
        return ResolvedPeerLabels(labels=labels, referenced_count=len(referenced_peer_ids))

    def referenced_peer_ids(self, changelog: NodeChangelog) -> set[str]:
        """Collect the IDs of every peer referenced by this changelog's relationships."""
        ids: set[str] = set()
        for relationship in changelog.relationships.values():
            if isinstance(relationship, RelationshipCardinalityOneChangelog):
                ids.update(peer_id for peer_id in (relationship.peer_id, relationship.peer_id_previous) if peer_id)
            elif isinstance(relationship, RelationshipCardinalityManyChangelog):
                ids.update(peer.peer_id for peer in relationship.peers if peer.peer_id)
        return ids
