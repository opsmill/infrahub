from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import DiffAction, RelationshipCardinality

if TYPE_CHECKING:
    from infrahub_sdk.diff import NodeDiff, NodeDiffElement, NodeDiffPeer

    from infrahub.core.diff.model.path import EnrichedDiffNode, EnrichedDiffRoot


class MergeDiffSerializer:
    """Serialize an enriched merge diff into the NodeDiff summary the selection predicates consume.

    Nodes are tagged with the merge target (destination) branch rather than the source branch the
    diff was computed on: post-merge the changed data lives on the target branch, which is also
    where selection runs its live lookups, so the tag stays valid even after the source branch is
    deleted. Actions are emitted as the uppercase enum name to match the proposed-change summary.
    Unchanged nodes and unchanged elements are dropped; a node whose only change was a conflict
    resolved to the base branch is still emitted, since it remains a real change for regeneration.
    """

    def serialize(self, root: EnrichedDiffRoot, target_branch_name: str) -> list[NodeDiff]:
        return [
            self._convert_node(node=node, target_branch_name=target_branch_name)
            for node in root.nodes
            if node.action != DiffAction.UNCHANGED
        ]

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
