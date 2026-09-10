from __future__ import annotations

import json
from typing import TYPE_CHECKING

from opentelemetry import trace

from infrahub.core.constants import DiffAction
from infrahub.core.constants.schema import HFID_ATTRIBUTE_NAME

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

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
        self,
        changelogs: Sequence[tuple[DiffAction, NodeChangelog]],
        resolvable_ids: Sequence[str],
        is_resolvable_kind: Callable[[str], bool],
    ) -> None:
        """Set the HFID of each changed node and of every relationship peer across the changelogs.

        ``resolvable_ids`` are the changed nodes whose HFID can be loaded; a peer outside that set is
        loaded on its own so a peer's HFID does not depend on whether the peer also changed.
        ``is_resolvable_kind`` gates that extra load: an external peer whose kind was dropped from
        the schema is left unresolved rather than joining the batch, so it cannot fail the load for
        every other external peer.
        """
        with trace.get_tracer(__name__).start_as_current_span("changelog.resolve_hfids") as span:
            span.set_attribute("changelog.changed_node_count", len(resolvable_ids))
            node_hfids = await self._label_loader.load_hfids(resolvable_ids)
            for action, changelog in changelogs:
                changelog.hfid = node_hfids.get(changelog.node_id)
                if changelog.hfid is None and action == DiffAction.REMOVED:
                    # A removed node is gone when the batch load runs, but the diff still records its HFID.
                    changelog.hfid = _hfid_from_diff(changelog)
            external_count = await self._fill_peer_hfids(
                changelogs=changelogs, node_hfids=node_hfids, is_resolvable_kind=is_resolvable_kind
            )
            span.set_attribute("changelog.external_peer_count", external_count)

    async def _fill_peer_hfids(
        self,
        changelogs: Sequence[tuple[DiffAction, NodeChangelog]],
        node_hfids: dict[str, list[str] | None],
        is_resolvable_kind: Callable[[str], bool],
    ) -> int:
        """Fill the HFID of every relationship peer; return how many were loaded on their own."""
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
            elif peer.peer_kind is not None and not is_resolvable_kind(peer.peer_kind):
                # The peer's kind is gone from the schema; leave its HFID unresolved so it never
                # fails the batch load that the other external peers share.
                continue
            else:
                external_ids.append(peer.peer_id)
        if not external_ids:
            return 0
        peer_hfids = await self._label_loader.load_hfids(external_ids)
        for peer in peers:
            if peer.peer_hfid is None and peer.peer_id in peer_hfids:
                peer.peer_hfid = peer_hfids[peer.peer_id]
        return len(set(external_ids))


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
