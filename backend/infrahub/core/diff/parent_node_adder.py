from dataclasses import dataclass, field

from infrahub.core.constants import DiffAction, RelationshipCardinality

from .model.path import EnrichedDiffNode, EnrichedDiffRelationship, EnrichedDiffRoot


@dataclass
class ParentNodeAddRequest:
    node_id: str
    parent_id: str
    parent_kind: str
    parent_label: str
    parent_rel_name: str
    parent_rel_identifier: str
    parent_rel_cardinality: RelationshipCardinality
    parent_rel_label: str = field(default="")


class DiffParentNodeAdder:
    def __init__(self) -> None:
        self._diff_root: EnrichedDiffRoot | None = None
        self._node_map: dict[str, EnrichedDiffNode] = {}

    def initialize(self, enriched_diff_root: EnrichedDiffRoot) -> None:
        self._diff_root = enriched_diff_root
        self._node_map = enriched_diff_root.get_node_map()

    def get_root(self) -> EnrichedDiffRoot:
        if not self._diff_root:
            raise RuntimeError("Must call initialize before using")
        return self._diff_root

    def get_node(self, node_uuid: str) -> EnrichedDiffNode:
        return self._node_map[node_uuid]

    def has_node(self, node_uuid: str) -> bool:
        return node_uuid in self._node_map

    def add_node(self, node: EnrichedDiffNode) -> None:
        if node.uuid in self._node_map:
            return
        self._node_map[node.uuid] = node
        self.get_root().nodes.add(node)

    def add_parent(self, parent_request: ParentNodeAddRequest) -> EnrichedDiffNode:
        if not self._diff_root:
            raise RuntimeError("Must call initialize before using")
        node = self.get_node(node_uuid=parent_request.node_id)
        if not self.has_node(node_uuid=parent_request.parent_id):
            parent = EnrichedDiffNode(
                uuid=parent_request.parent_id,
                kind=parent_request.parent_kind,
                label=parent_request.parent_label,
                action=DiffAction.UNCHANGED,
                changed_at=None,
            )
            self.add_node(parent)
        else:
            parent = self.get_node(node_uuid=parent_request.parent_id)

        try:
            rel = node.get_relationship(name=parent_request.parent_rel_name)
            rel.nodes.add(parent)
        except ValueError:
            node.relationships.add(
                EnrichedDiffRelationship(
                    name=parent_request.parent_rel_name,
                    identifier=parent_request.parent_rel_identifier,
                    label=parent_request.parent_rel_label,
                    cardinality=parent_request.parent_rel_cardinality,
                    changed_at=None,
                    action=DiffAction.UNCHANGED,
                    nodes={parent},
                )
            )

        return parent
