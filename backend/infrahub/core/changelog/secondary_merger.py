from __future__ import annotations

from typing import TYPE_CHECKING

from .models import RelationshipCardinalityManyChangelog

if TYPE_CHECKING:
    from .models import NodeChangelog


class SecondaryChangelogMerger:
    """Collapses secondary changelogs so each affected peer yields a single one.

    A mutation can change several relationships to the same peer, and each produces its own
    secondary for that peer; emitting them separately would deliver duplicate events.
    """

    def merge(self, secondaries: list[NodeChangelog]) -> list[NodeChangelog]:
        """Fold every secondary into the first changelog seen for its peer.

        Each distinct reciprocal relationship the later secondaries carry is kept.
        """
        merged: dict[str, NodeChangelog] = {}
        for secondary in secondaries:
            existing = merged.get(secondary.node_id)
            if existing is None:
                merged[secondary.node_id] = secondary
                continue
            if existing.parent is None and secondary.parent is not None:
                existing.add_parent(parent=secondary.parent)
            self._merge_relationships(existing=existing, secondary=secondary)
        return list(merged.values())

    def _merge_relationships(self, existing: NodeChangelog, secondary: NodeChangelog) -> None:
        for name, relationship in secondary.relationships.items():
            current = existing.relationships.get(name)
            if current is None:
                existing.relationships[name] = relationship
            elif isinstance(current, RelationshipCardinalityManyChangelog) and isinstance(
                relationship, RelationshipCardinalityManyChangelog
            ):
                # Two source relationships resolved to the same many peer-side name; keep every
                # distinct peer change rather than dropping the later relationship's entries.
                seen = {(peer.peer_id, peer.peer_status) for peer in current.peers}
                for peer in relationship.peers:
                    key = (peer.peer_id, peer.peer_status)
                    if key in seen:
                        continue
                    seen.add(key)
                    current.peers.append(peer)
