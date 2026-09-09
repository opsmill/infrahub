from __future__ import annotations

import json
from typing import TYPE_CHECKING

from infrahub.core.constants import DiffAction
from infrahub.core.constants.schema import HFID_ATTRIBUTE_NAME

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .enrichment import NodeLabelLoader
    from .models import NodeChangelog


class ChangelogHfidResolver:
    """Fill the HFID of changed nodes and their relationship peers on already-built changelogs.

    The diff carries display labels but not HFIDs, so they are resolved here through batched loads
    once the changelog structure exists.
    """

    def __init__(self, label_loader: NodeLabelLoader) -> None:
        self._label_loader = label_loader

    async def enrich(
        self, changelogs: Sequence[tuple[DiffAction, NodeChangelog]], resolvable_ids: Sequence[str]
    ) -> None:
        """Set the HFID of each changed node and of every relationship peer across the changelogs.

        ``resolvable_ids`` are the changed nodes whose HFID can be loaded; a peer outside that set is
        loaded on its own so a peer's HFID does not depend on whether the peer also changed.
        """
        node_hfids = await self._label_loader.load_hfids(resolvable_ids)
        for action, changelog in changelogs:
            changelog.hfid = node_hfids.get(changelog.node_id)
            if changelog.hfid is None and action == DiffAction.REMOVED:
                # A removed node is gone when the batch load runs, but the diff still records its HFID.
                changelog.hfid = _hfid_from_diff(changelog)
        await self._fill_peer_hfids(changelogs=changelogs, node_hfids=node_hfids)

    async def _fill_peer_hfids(
        self,
        changelogs: Sequence[tuple[DiffAction, NodeChangelog]],
        node_hfids: dict[str, list[str] | None],
    ) -> None:
        peers = [
            peer
            for _, changelog in changelogs
            for relationship in changelog.relationships.values()
            for peer in relationship.peer_entries()
        ]
        external_ids: list[str] = []
        for peer in peers:
            if not peer.peer_id:
                continue
            if peer.peer_id in node_hfids:
                peer.peer_hfid = node_hfids[peer.peer_id]
            else:
                external_ids.append(peer.peer_id)
        if not external_ids:
            return
        peer_hfids = await self._label_loader.load_hfids(external_ids)
        for peer in peers:
            if peer.peer_hfid is None and peer.peer_id in peer_hfids:
                peer.peer_hfid = peer_hfids[peer.peer_id]


def _hfid_from_diff(node_changelog: NodeChangelog) -> list[str] | None:
    """Recover a node's HFID from the human-friendly-id attribute the diff carries for it."""
    attribute = node_changelog.attributes.get(HFID_ATTRIBUTE_NAME)
    if attribute is None:
        return None
    raw = attribute.value if attribute.value is not None else attribute.value_previous
    if not isinstance(raw, str):
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, list) else None
