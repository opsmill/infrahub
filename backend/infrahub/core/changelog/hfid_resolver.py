from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

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
    once the changelog structure exists. A peer display label the diff could not give is filled in
    the same pass, so a peer never carries an HFID without its display label.
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

        A peer the diff left without a display label takes the one of its own changelog when the peer
        changed too, and is otherwise loaded with its HFID.

        ``resolvable_ids`` are the changed nodes whose HFID can be loaded; a peer outside that set is
        loaded on its own so a peer's HFID does not depend on whether the peer also changed.
        ``is_resolvable_kind`` gates that extra load: an external peer whose kind was dropped from
        the schema is left unresolved rather than joining the batch, so it cannot fail the load for
        every other external peer. A node whose HFID the diff carries as a current value (created,
        or HFID changed) takes it from the diff instead of being loaded.
        """
        with trace.get_tracer(__name__).start_as_current_span("changelog.resolve_hfids") as span:
            span.set_attribute("changelog.resolvable_node_count", len(resolvable_ids))
            # A node whose kind is gone stays unresolved, as its peers do, even when the diff carries its HFID.
            node_hfids: dict[str, list[str] | None] = {
                changelog.node_id: hfid
                for _, changelog in changelogs
                if is_resolvable_kind(changelog.node_kind) and (hfid := _current_hfid_from_diff(changelog)) is not None
            }
            span.set_attribute("changelog.diff_hfid_count", len(node_hfids))
            ids_to_load = [node_id for node_id in resolvable_ids if node_id not in node_hfids]
            node_hfids.update(await self._label_loader.load_hfids(ids_to_load))
            for action, changelog in changelogs:
                if (
                    node_hfids.get(changelog.node_id) is None
                    and action == DiffAction.REMOVED
                    and is_resolvable_kind(changelog.node_kind)
                    and (previous_hfid := _hfid_from_diff(changelog)) is not None
                ):
                    # A removed node is gone when the batch load runs, but the diff still records its HFID.
                    node_hfids[changelog.node_id] = previous_hfid
                changelog.hfid = node_hfids.get(changelog.node_id)
            node_display_labels = {changelog.node_id: changelog.display_label for _, changelog in changelogs}
            external_count = await self._fill_peer_hfids(
                changelogs=changelogs,
                node_hfids=node_hfids,
                node_display_labels=node_display_labels,
                is_resolvable_kind=is_resolvable_kind,
            )
            span.set_attribute("changelog.external_peer_count", external_count)

    async def _fill_peer_hfids(
        self,
        changelogs: Sequence[tuple[DiffAction, NodeChangelog]],
        node_hfids: dict[str, list[str] | None],
        node_display_labels: dict[str, str],
        is_resolvable_kind: Callable[[str], bool],
    ) -> int:
        """Fill the HFID and any missing display label of every relationship peer.

        Return how many peers were loaded on their own.
        """
        peers = [
            peer
            for _, changelog in changelogs
            for relationship in changelog.relationships.values()
            for peer in relationship.peer_entries()
        ]
        external_ids: list[str] = []
        unlabeled_external_ids: set[str] = set()
        for peer in peers:
            if not peer.peer_id:
                continue
            if peer.peer_id in node_hfids:
                peer.peer_hfid = node_hfids[peer.peer_id]
                if peer.peer_display_label is None:
                    peer.peer_display_label = node_display_labels.get(peer.peer_id)
            elif peer.peer_kind is not None and not is_resolvable_kind(peer.peer_kind):
                # The peer's kind is gone from the schema; leave its HFID unresolved so it never
                # fails the batch load that the other external peers share.
                continue
            else:
                external_ids.append(peer.peer_id)
                if peer.peer_display_label is None:
                    unlabeled_external_ids.add(peer.peer_id)
        if not external_ids:
            return 0
        peer_hfids = await self._label_loader.load_hfids(
            [peer_id for peer_id in external_ids if peer_id not in unlabeled_external_ids]
        )
        peer_labels = await self._label_loader.load_labels(
            [peer_id for peer_id in external_ids if peer_id in unlabeled_external_ids]
        )
        peer_hfids.update({peer_id: labels.hfid for peer_id, labels in peer_labels.items()})
        peer_display_labels = {peer_id: labels.display_label for peer_id, labels in peer_labels.items()}
        for peer in peers:
            if peer.peer_hfid is None and peer.peer_id in peer_hfids:
                peer.peer_hfid = peer_hfids[peer.peer_id]
            if peer.peer_display_label is None and peer.peer_id in peer_display_labels:
                peer.peer_display_label = peer_display_labels[peer.peer_id]
        return len(peer_hfids)


def _hfid_from_diff(node_changelog: NodeChangelog) -> list[str] | None:
    """Recover a node's HFID from the human-friendly-id attribute the diff carries for it.

    The current value is used when the diff has one, the previous value otherwise, so a removed
    node's HFID is recovered from what it was before the removal.
    """
    attribute = node_changelog.attributes.get(HFID_ATTRIBUTE_NAME)
    if attribute is None:
        return None
    return _parse_hfid(attribute.value if attribute.value is not None else attribute.value_previous)


def _current_hfid_from_diff(node_changelog: NodeChangelog) -> list[str] | None:
    """Return the node's HFID when the diff carries it as a current value, None otherwise."""
    attribute = node_changelog.attributes.get(HFID_ATTRIBUTE_NAME)
    if attribute is None:
        return None
    return _parse_hfid(attribute.value)


def _parse_hfid(raw: Any) -> list[str] | None:
    """Parse the stored form of an HFID attribute, a JSON-encoded list, or None when it is not one."""
    if not isinstance(raw, str):
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, list) else None
