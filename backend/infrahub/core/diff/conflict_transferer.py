from .combiner import DiffCombiner
from .model.path import (
    EnrichedDiffAttribute,
    EnrichedDiffNode,
    EnrichedDiffRelationship,
    EnrichedDiffRoot,
    EnrichedDiffSingleRelationship,
)


class DiffConflictTransferer:
    def __init__(self, diff_combiner: DiffCombiner):
        self.diff_combiner = diff_combiner

    async def transfer(self, earlier: EnrichedDiffRoot, later: EnrichedDiffRoot) -> None:
        earlier_node_map = {n.uuid: n for n in earlier.nodes}
        later_node_map = {n.uuid: n for n in later.nodes}
        common_node_uuids = set(earlier_node_map.keys()) & set(later_node_map.keys())
        for node_uuid in common_node_uuids:
            earlier_node = earlier_node_map[node_uuid]
            later_node = later_node_map[node_uuid]
            self._transfer_node_conflicts(earlier=earlier_node, later=later_node)

    def _transfer_node_conflicts(self, earlier: EnrichedDiffNode, later: EnrichedDiffNode) -> None:
        if earlier.action is later.action:
            later.conflict = self.diff_combiner.combine_conflicts(earlier=earlier.conflict, later=later.conflict)

        earlier_attribute_map = {a.name: a for a in earlier.attributes}
        later_attribute_map = {a.name: a for a in later.attributes}
        common_attribute_names = set(earlier_attribute_map.keys()) & set(later_attribute_map.keys())
        for attr_name in common_attribute_names:
            earlier_attribute = earlier_attribute_map[attr_name]
            later_attribute = later_attribute_map[attr_name]
            self._transfer_property_conflicts(earlier=earlier_attribute, later=later_attribute)
        earlier_relationship_map = {r.name: r for r in earlier.relationships}
        later_relationship_map = {r.name: r for r in later.relationships}
        common_relationship_names = set(earlier_relationship_map.keys()) & set(later_relationship_map.keys())
        for relationship_name in common_relationship_names:
            earlier_relationship = earlier_relationship_map[relationship_name]
            later_relationship = later_relationship_map[relationship_name]
            self._transfer_relationship_conflicts(
                earlier=earlier_relationship,
                later=later_relationship,
            )

    def _transfer_property_conflicts(
        self,
        earlier: EnrichedDiffAttribute | EnrichedDiffSingleRelationship,
        later: EnrichedDiffAttribute | EnrichedDiffSingleRelationship,
    ) -> None:
        earlier_property_map = {p.property_type: p for p in earlier.properties}
        later_property_map = {p.property_type: p for p in later.properties}
        common_property_types = set(earlier_property_map.keys()) & set(later_property_map.keys())
        for property_type in common_property_types:
            earlier_property = earlier_property_map[property_type]
            later_property = later_property_map[property_type]
            later_property.conflict = self.diff_combiner.combine_conflicts(
                earlier=earlier_property.conflict, later=later_property.conflict
            )

    def _transfer_relationship_conflicts(
        self,
        earlier: EnrichedDiffRelationship,
        later: EnrichedDiffRelationship,
    ) -> None:
        earlier_elements_by_peer_id = {element.peer_id: element for element in earlier.relationships}
        later_elements_by_peer_id = {element.peer_id: element for element in later.relationships}
        common_peer_ids = set(earlier_elements_by_peer_id.keys()) & set(later_elements_by_peer_id.keys())
        for peer_id in common_peer_ids:
            earlier_element = earlier_elements_by_peer_id[peer_id]
            later_element = later_elements_by_peer_id[peer_id]
            later_element.conflict = self.diff_combiner.combine_conflicts(
                earlier=earlier_element.conflict, later=later_element.conflict
            )
            self._transfer_property_conflicts(earlier=earlier_element, later=later_element)
