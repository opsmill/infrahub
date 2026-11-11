from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.diff import NodeDiff
from pydantic import TypeAdapter

from infrahub.core.constants import DiffAction, RelationshipCardinality

if TYPE_CHECKING:
    from infrahub_sdk.diff import NodeDiffElement, NodeDiffPeer

    from infrahub.core.diff.model.path import EnrichedDiffNode, EnrichedDiffRoot
    from infrahub.core.timestamp import Timestamp

_NODE_DIFFS_ADAPTER = TypeAdapter(list[NodeDiff])


class DiffSummarySerializer:
    """Build the node-diff summary from an enriched diff root and encode it for caching.

    Unchanged nodes and elements are omitted from the summary. ``dump`` and ``load`` are the
    inverse halves of the cached JSON encoding.
    """

    def serialize(
        self, root: EnrichedDiffRoot, target_branch_name: str, unchanged_as_updated: bool = False
    ) -> list[NodeDiff]:
        """Build the summary of a diff root.

        With ``unchanged_as_updated``, unchanged nodes and elements that have a change time are kept as updated
        ones. A diff of a time range calculated with its unchanged entries holds only what changed in that
        range, including a value changed back to the one of the base branch. A parent node or relationship
        added to show where a changed node sits has no change time, so it stays omitted.
        """
        return [
            self._convert_node(
                node=node, target_branch_name=target_branch_name, unchanged_as_updated=unchanged_as_updated
            )
            for node in root.nodes
            if _is_kept(action=node.action, changed_at=node.changed_at, unchanged_as_updated=unchanged_as_updated)
        ]

    def dump(self, diff_summary: list[NodeDiff]) -> str:
        return _NODE_DIFFS_ADAPTER.dump_json(diff_summary).decode()

    def load(self, payload: str | bytes) -> list[NodeDiff]:
        return _NODE_DIFFS_ADAPTER.validate_json(payload)

    def _convert_node(self, node: EnrichedDiffNode, target_branch_name: str, unchanged_as_updated: bool) -> NodeDiff:
        def action_name(action: DiffAction) -> str:
            if unchanged_as_updated and action == DiffAction.UNCHANGED:
                return DiffAction.UPDATED.name
            return action.name

        elements: list[NodeDiffElement] = []
        for attribute in node.attributes:
            if attribute.action == DiffAction.UNCHANGED and not unchanged_as_updated:
                continue
            elements.append(
                {
                    "name": attribute.name,
                    "element_type": "ATTRIBUTE",
                    "action": action_name(attribute.action),
                    "summary": {
                        "added": attribute.num_added,
                        "updated": attribute.num_updated,
                        "removed": attribute.num_removed,
                    },
                }
            )
        for relationship in node.relationships:
            if not relationship.include_in_response and not (
                unchanged_as_updated and relationship.changed_at is not None
            ):
                continue
            is_cardinality_one = relationship.cardinality == RelationshipCardinality.ONE
            element: NodeDiffElement = {
                "name": relationship.name,
                "element_type": "RELATIONSHIP_ONE" if is_cardinality_one else "RELATIONSHIP_MANY",
                "action": action_name(relationship.action),
                "summary": {
                    "added": relationship.num_added,
                    "updated": relationship.num_updated,
                    "removed": relationship.num_removed,
                },
            }
            if not is_cardinality_one:
                peers: list[NodeDiffPeer] = [
                    {
                        "action": action_name(peer.action),
                        "summary": {
                            "added": peer.num_added,
                            "updated": peer.num_updated,
                            "removed": peer.num_removed,
                        },
                    }
                    for peer in relationship.relationships
                ]
                element["peers"] = peers
            elements.append(element)

        return {
            "branch": target_branch_name,
            "kind": node.kind,
            "id": node.uuid,
            "action": action_name(node.action),
            "display_label": node.label,
            "elements": elements,
        }


def _is_kept(*, action: DiffAction, changed_at: Timestamp | None, unchanged_as_updated: bool) -> bool:
    if action != DiffAction.UNCHANGED:
        return True
    return unchanged_as_updated and changed_at is not None
