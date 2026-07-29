from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.diff import NodeDiff
from pydantic import TypeAdapter

from infrahub.core.constants import DiffAction, RelationshipCardinality

if TYPE_CHECKING:
    from infrahub_sdk.diff import NodeDiffElement, NodeDiffPeer

    from infrahub.core.diff.model.path import EnrichedDiffNode, EnrichedDiffRoot

_NODE_DIFFS_ADAPTER = TypeAdapter(list[NodeDiff])


class DiffSummarySerializer:
    """Build the node-diff summary from an enriched diff root and encode it for caching.

    Unchanged nodes and elements are omitted from the summary. ``dump`` and ``load`` are the
    inverse halves of the cached JSON encoding.
    """

    def serialize(self, root: EnrichedDiffRoot, target_branch_name: str) -> list[NodeDiff]:
        return [
            self._convert_node(node=node, target_branch_name=target_branch_name)
            for node in root.nodes
            if node.action != DiffAction.UNCHANGED
        ]

    def dump(self, diff_summary: list[NodeDiff]) -> str:
        return _NODE_DIFFS_ADAPTER.dump_json(diff_summary).decode()

    def load(self, payload: str | bytes) -> list[NodeDiff]:
        return _NODE_DIFFS_ADAPTER.validate_json(payload)

    def _convert_node(self, node: EnrichedDiffNode, target_branch_name: str) -> NodeDiff:
        elements: list[NodeDiffElement] = []
        for attribute in node.attributes:
            if attribute.action == DiffAction.UNCHANGED:
                continue
            elements.append(
                {
                    "name": attribute.name,
                    "element_type": "ATTRIBUTE",
                    "action": attribute.action.name,
                    "summary": {
                        "added": attribute.num_added,
                        "updated": attribute.num_updated,
                        "removed": attribute.num_removed,
                    },
                }
            )
        for relationship in node.relationships:
            if not relationship.include_in_response:
                continue
            is_cardinality_one = relationship.cardinality == RelationshipCardinality.ONE
            element: NodeDiffElement = {
                "name": relationship.name,
                "element_type": "RELATIONSHIP_ONE" if is_cardinality_one else "RELATIONSHIP_MANY",
                "action": relationship.action.name,
                "summary": {
                    "added": relationship.num_added,
                    "updated": relationship.num_updated,
                    "removed": relationship.num_removed,
                },
            }
            if not is_cardinality_one:
                peers: list[NodeDiffPeer] = [
                    {
                        "action": peer.action.name,
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
            "action": node.action.name,
            "display_label": node.label,
            "elements": elements,
        }
