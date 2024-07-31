from dataclasses import dataclass, field
from uuid import uuid4

from infrahub.core.constants import DiffAction

from .model.path import EnrichedDiffNode, EnrichedDiffRoot


@dataclass
class NodePair:
    earlier: EnrichedDiffNode | None = field(default=None)
    later: EnrichedDiffNode | None = field(default=None)


class DiffCombiner:
    def __init__(self) -> None:
        self._child_parent_uuid_map: dict[str, str] = {}
        self._parent_node_uuids: set[str] = set()
        self._earlier_nodes_by_uuid: dict[str, EnrichedDiffNode] = {}
        self._later_nodes_by_uuid: dict[str, EnrichedDiffNode] = {}
        self._common_node_uuids: set[str] = set()

    def _initialize(self, earlier_diff: EnrichedDiffRoot, later_diff: EnrichedDiffRoot) -> None:
        self._child_parent_uuid_map = {}
        self._earlier_nodes_by_uuid = {}
        self._later_nodes_by_uuid = {}
        self._common_node_uuids = set()
        # map the parent of each node (if it exists), preference to the later diff
        for diff_root in (earlier_diff, later_diff):
            for node in diff_root.nodes:
                for rel in node.relationships:
                    for child_node in rel.nodes:
                        self._child_parent_uuid_map[child_node.uuid] = node.uuid
        # UUIDs of all the parents, removing the stale parents from the earlier diff
        self._parent_node_uuids = set(self._child_parent_uuid_map.values())
        self._earlier_nodes_by_uuid = {n.uuid: n for n in earlier_diff.nodes}
        self._later_nodes_by_uuid = {n.uuid: n for n in later_diff.nodes}
        self._common_node_uuids = set(self._earlier_nodes_by_uuid.keys()) & set(self._later_nodes_by_uuid.keys())

    def _filter_nodes_to_keep(self, earlier_diff: EnrichedDiffRoot, later_diff: EnrichedDiffRoot) -> list[NodePair]:
        filtered_node_pairs: list[NodePair] = []
        for earlier_node in earlier_diff.nodes:
            later_node: EnrichedDiffNode | None = None
            if earlier_node.uuid in self._common_node_uuids:
                later_node = self._later_nodes_by_uuid[earlier_node.uuid]
            # this is an out-of-date parent
            if (
                earlier_node.action is DiffAction.UNCHANGED
                and (later_node is None or later_node.action is DiffAction.UNCHANGED)
                and earlier_node not in self._parent_node_uuids
            ):
                continue
            if later_node is None:
                filtered_node_pairs.append(NodePair(earlier=earlier_node))
                continue
            # if node was added and removed or vice-versa, remove it from the diff
            if {earlier_node.action, later_node.action} == {DiffAction.ADDED, DiffAction.REMOVED}:
                continue
            filtered_node_pairs.append(NodePair(earlier=earlier_node, later=later_node))
        for later_node in later_diff.nodes:
            # these have already been handled
            if later_node.uuid in self._common_node_uuids:
                continue
            filtered_node_pairs.append(NodePair(later=later_node))
        return filtered_node_pairs

    # def _combine_attributes(
    #     self, earlier_attributes: set[EnrichedDiffAttribute], later_attributes: set[EnrichedDiffAttribute]
    # ) -> set[EnrichedDiffAttribute]: ...

    # def _combine_relationships(
    #     self, earlier_relationships: set[EnrichedDiffRelationship], later_relationships: set[EnrichedDiffRelationship]
    # ) -> set[EnrichedDiffRelationship]: ...

    def _combine_nodes(self, node_pairs: list[NodePair]) -> set[EnrichedDiffNode]:
        combined_nodes: set[EnrichedDiffNode] = set()
        for node_pair in node_pairs:
            if node_pair.earlier is None:
                if node_pair.later is not None:
                    combined_nodes.add(node_pair.later)
                continue
            if node_pair.later is None:
                if node_pair.earlier is not None:
                    combined_nodes.add(node_pair.earlier)
                continue
            # attributes = self._combine_attributes(
            #     earlier_attributes=node_pair.earlier.attributes, later_attributes=node_pair.later.attributes
            # )
            # relationships = self._combine_relationships(
            #     earlier_relationships=node_pair.earlier.relationships, later_relationships=node_pair.later.relationships
            # )
            actions = {node_pair.earlier.action, node_pair.later.action}
            combined_action = DiffAction.UPDATED
            if DiffAction.ADDED in actions:
                combined_action = DiffAction.ADDED
            elif DiffAction.REMOVED in actions:
                combined_action = DiffAction.REMOVED
            elif actions == {DiffAction.UNCHANGED}:
                combined_action = DiffAction.UNCHANGED
            combined_nodes.add(
                EnrichedDiffNode(
                    uuid=node_pair.later.uuid,
                    kind=node_pair.later.kind,
                    label=node_pair.later.label,
                    changed_at=node_pair.later.changed_at,
                    action=combined_action,
                    attributes=set(),
                    relationships=set(),
                )
            )
        return combined_nodes

    async def combine(self, earlier_diff: EnrichedDiffRoot, later_diff: EnrichedDiffRoot) -> EnrichedDiffRoot:
        self._initialize(earlier_diff=earlier_diff, later_diff=later_diff)
        filtered_node_pairs = self._filter_nodes_to_keep(earlier_diff=earlier_diff, later_diff=later_diff)
        combined_nodes = self._combine_nodes(node_pairs=filtered_node_pairs)
        return EnrichedDiffRoot(
            uuid=str(uuid4()),
            base_branch_name=later_diff.base_branch_name,
            diff_branch_name=later_diff.diff_branch_name,
            from_time=earlier_diff.from_time,
            to_time=later_diff.to_time,
            nodes=combined_nodes,
        )
