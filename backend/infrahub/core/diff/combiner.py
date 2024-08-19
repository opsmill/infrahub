from copy import deepcopy
from dataclasses import dataclass, field
from typing import Iterable
from uuid import uuid4

from infrahub.core import registry
from infrahub.core.constants import DiffAction, RelationshipCardinality

from .model.path import (
    EnrichedDiffAttribute,
    EnrichedDiffConflict,
    EnrichedDiffNode,
    EnrichedDiffProperty,
    EnrichedDiffRelationship,
    EnrichedDiffRoot,
    EnrichedDiffSingleRelationship,
)


@dataclass
class NodePair:
    earlier: EnrichedDiffNode | None = field(default=None)
    later: EnrichedDiffNode | None = field(default=None)


class DiffCombiner:
    def __init__(self) -> None:
        self.schema_manager = registry.schema
        # {child_uuid: (parent_uuid, parent_rel_name)}
        self._child_parent_uuid_map: dict[str, tuple[str, str]] = {}
        self._parent_node_uuids: set[str] = set()
        self._earlier_nodes_by_uuid: dict[str, EnrichedDiffNode] = {}
        self._later_nodes_by_uuid: dict[str, EnrichedDiffNode] = {}
        self._common_node_uuids: set[str] = set()
        self._diff_branch_name: str | None = None

    def _initialize(self, earlier_diff: EnrichedDiffRoot, later_diff: EnrichedDiffRoot) -> None:
        self._diff_branch_name = earlier_diff.diff_branch_name
        self._child_parent_uuid_map = {}
        self._earlier_nodes_by_uuid = {}
        self._later_nodes_by_uuid = {}
        self._common_node_uuids = set()
        # map the parent of each node (if it exists), preference to the later diff
        for diff_root in (earlier_diff, later_diff):
            for child_node in diff_root.nodes:
                for parent_rel in child_node.relationships:
                    for parent_node in parent_rel.nodes:
                        self._child_parent_uuid_map[child_node.uuid] = (parent_node.uuid, parent_rel.name)
        # UUIDs of all the parents, removing the stale parents from the earlier diff
        self._parent_node_uuids = {parent_tuple[0] for parent_tuple in self._child_parent_uuid_map.values()}
        self._earlier_nodes_by_uuid = {n.uuid: n for n in earlier_diff.nodes}
        self._later_nodes_by_uuid = {n.uuid: n for n in later_diff.nodes}
        self._common_node_uuids = set(self._earlier_nodes_by_uuid.keys()) & set(self._later_nodes_by_uuid.keys())

    @property
    def diff_branch_name(self) -> str:
        if not self._diff_branch_name:
            raise RuntimeError("DiffCombiner is not initialized")
        return self._diff_branch_name

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
                and earlier_node.uuid not in self._parent_node_uuids
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

    def _should_include(self, earlier: DiffAction, later: DiffAction) -> bool:
        actions = {earlier, later}
        if actions == {DiffAction.UNCHANGED}:
            return False
        if actions == {DiffAction.ADDED, DiffAction.REMOVED}:
            return False
        return True

    def _combine_actions(self, earlier: DiffAction, later: DiffAction) -> DiffAction:
        actions = {earlier, later}
        combined_action = DiffAction.UPDATED
        if DiffAction.ADDED in actions:
            combined_action = DiffAction.ADDED
        elif DiffAction.REMOVED in actions:
            combined_action = DiffAction.REMOVED
        elif actions == {DiffAction.UNCHANGED}:
            combined_action = DiffAction.UNCHANGED
        return combined_action

    def _combined_conflicts(self, earlier: EnrichedDiffConflict, later: EnrichedDiffConflict) -> EnrichedDiffConflict:
        # TODO
        raise NotImplementedError()

    def _combine_properties(
        self, earlier_properties: set[EnrichedDiffProperty], later_properties: set[EnrichedDiffProperty]
    ) -> set[EnrichedDiffProperty]:
        earlier_props_by_type = {prop.property_type: prop for prop in earlier_properties}
        later_props_by_type = {prop.property_type: prop for prop in later_properties}
        common_property_types = set(earlier_props_by_type.keys()) & set(later_props_by_type.keys())
        combined_properties: set[EnrichedDiffProperty] = set()
        for earlier_property in earlier_properties:
            if earlier_property.property_type not in common_property_types:
                combined_properties.add(deepcopy(earlier_property))
                continue
            later_property = later_props_by_type[earlier_property.property_type]
            if not self._should_include(earlier=earlier_property.action, later=later_property.action):
                continue
            combined_property = EnrichedDiffProperty(
                property_type=later_property.property_type,
                changed_at=later_property.changed_at,
                previous_value=earlier_property.previous_value,
                new_value=later_property.new_value,
                path_identifier=later_property.path_identifier,
                action=self._combine_actions(earlier=earlier_property.action, later=later_property.action),
            )
            combined_properties.add(combined_property)
        combined_properties |= {
            deepcopy(prop) for prop in later_properties if prop.property_type not in common_property_types
        }
        return combined_properties

    def _combine_attributes(
        self, earlier_attributes: set[EnrichedDiffAttribute], later_attributes: set[EnrichedDiffAttribute]
    ) -> set[EnrichedDiffAttribute]:
        earlier_attrs_by_name = {attr.name: attr for attr in earlier_attributes}
        later_attrs_by_name = {attr.name: attr for attr in later_attributes}
        common_attr_names = set(earlier_attrs_by_name.keys()) & set(later_attrs_by_name.keys())
        combined_attributes: set[EnrichedDiffAttribute] = set()
        for earlier_attribute in earlier_attributes:
            if earlier_attribute.name not in common_attr_names:
                combined_attributes.add(deepcopy(earlier_attribute))
                continue
            later_attribute = later_attrs_by_name[earlier_attribute.name]
            if not self._should_include(earlier=earlier_attribute.action, later=later_attribute.action):
                continue
            combined_action = self._combine_actions(earlier=earlier_attribute.action, later=later_attribute.action)
            combined_attribute = EnrichedDiffAttribute(
                name=later_attribute.name,
                changed_at=later_attribute.changed_at,
                action=combined_action,
                path_identifier=later_attribute.path_identifier,
                properties=self._combine_properties(
                    earlier_properties=earlier_attribute.properties, later_properties=later_attribute.properties
                ),
            )
            combined_attributes.add(combined_attribute)
        combined_attributes |= {
            deepcopy(attribute) for attribute in later_attributes if attribute.name not in common_attr_names
        }
        return combined_attributes

    def _combine_cardinality_one_relationship_elements(
        self, elements: Iterable[EnrichedDiffSingleRelationship]
    ) -> EnrichedDiffSingleRelationship:
        ordered_elements = sorted(elements, key=lambda e: e.changed_at)
        if len(ordered_elements) < 2:
            return deepcopy(next(iter(elements)))
        combined_action = ordered_elements[0].action
        combined_properties = ordered_elements[0].properties
        for element in ordered_elements[1:]:
            combined_action = self._combine_actions(earlier=combined_action, later=element.action)
            combined_properties = self._combine_properties(
                earlier_properties=combined_properties, later_properties=element.properties
            )
        final_element = ordered_elements[-1]
        return EnrichedDiffSingleRelationship(
            changed_at=final_element.changed_at,
            action=combined_action,
            peer_id=final_element.peer_id,
            peer_label=final_element.peer_label,
            path_identifier=final_element.path_identifier,
            properties=combined_properties,
        )

    def _combined_cardinality_many_relationship_elements(
        self, earlier_elements: set[EnrichedDiffSingleRelationship], later_elements: set[EnrichedDiffSingleRelationship]
    ) -> set[EnrichedDiffSingleRelationship]:
        earlier_elements_by_peer_id = {element.peer_id: element for element in earlier_elements}
        later_elements_by_peer_id = {element.peer_id: element for element in later_elements}
        common_peer_ids = set(earlier_elements_by_peer_id.keys()) & set(later_elements_by_peer_id.keys())
        combined_elements: set[EnrichedDiffSingleRelationship] = set()
        for earlier_element in earlier_elements:
            if earlier_element.peer_id not in common_peer_ids:
                combined_elements.add(deepcopy(earlier_element))
                continue
            later_element = later_elements_by_peer_id[earlier_element.peer_id]
            if not self._should_include(earlier=earlier_element.action, later=later_element.action):
                continue
            combined_element = EnrichedDiffSingleRelationship(
                changed_at=later_element.changed_at,
                action=self._combine_actions(earlier=earlier_element.action, later=later_element.action),
                peer_id=later_element.peer_id,
                peer_label=later_element.peer_label,
                path_identifier=later_element.path_identifier,
                properties=self._combine_properties(
                    earlier_properties=earlier_element.properties, later_properties=later_element.properties
                ),
            )
            combined_elements.add(combined_element)
        combined_elements |= {
            deepcopy(later_element) for later_element in later_elements if later_element.peer_id not in common_peer_ids
        }
        return combined_elements

    def _combine_relationships(
        self,
        earlier_relationships: set[EnrichedDiffRelationship],
        later_relationships: set[EnrichedDiffRelationship],
        node_kind: str,
    ) -> set[EnrichedDiffRelationship]:
        node_schema = self.schema_manager.get_node_schema(name=node_kind, branch=self.diff_branch_name, duplicate=False)
        earlier_rels_by_name = {rel.name: rel for rel in earlier_relationships}
        later_rels_by_name = {rel.name: rel for rel in later_relationships}
        common_rel_names = set(earlier_rels_by_name.keys()) & set(later_rels_by_name.keys())
        combined_relationships: set[EnrichedDiffRelationship] = set()
        for earlier_relationship in earlier_relationships:
            if earlier_relationship.name not in common_rel_names:
                copied = deepcopy(earlier_relationship)
                copied.nodes = set()
                combined_relationships.add(copied)
                continue
            relationship_schema = node_schema.get_relationship(name=earlier_relationship.name)
            is_cardinality_one = relationship_schema.cardinality is RelationshipCardinality.ONE
            later_relationship = later_rels_by_name[earlier_relationship.name]
            if len(earlier_relationship.relationships) == 0 and len(later_relationship.relationships) == 0:
                combined_relationship_elements = set()
            elif is_cardinality_one:
                combined_relationship_elements = {
                    self._combine_cardinality_one_relationship_elements(
                        elements=(earlier_relationship.relationships | later_relationship.relationships)
                    )
                }
            else:
                combined_relationship_elements = self._combined_cardinality_many_relationship_elements(
                    earlier_elements=earlier_relationship.relationships, later_elements=later_relationship.relationships
                )
            combined_relationship = EnrichedDiffRelationship(
                name=later_relationship.name,
                label=later_relationship.label,
                changed_at=later_relationship.changed_at or earlier_relationship.changed_at,
                action=self._combine_actions(earlier=earlier_relationship.action, later=later_relationship.action),
                path_identifier=later_relationship.path_identifier,
                relationships=combined_relationship_elements,
                nodes=set(),
            )
            combined_relationships.add(combined_relationship)
        for later_relationship in later_relationships:
            if later_relationship.name in common_rel_names:
                continue
            copied = deepcopy(later_relationship)
            copied.nodes = set()
            combined_relationships.add(copied)
        return combined_relationships

    def _combine_nodes(self, node_pairs: list[NodePair]) -> set[EnrichedDiffNode]:
        combined_nodes: set[EnrichedDiffNode] = set()
        for node_pair in node_pairs:
            if node_pair.earlier is None:
                if node_pair.later is not None:
                    copied = deepcopy(node_pair.later)
                    for rel in copied.relationships:
                        rel.nodes = set()
                        rel.reset_summaries()
                    combined_nodes.add(copied)
                continue
            if node_pair.later is None:
                if node_pair.earlier is not None:
                    copied = deepcopy(node_pair.earlier)
                    for rel in copied.relationships:
                        rel.nodes = set()
                        rel.reset_summaries()
                    combined_nodes.add(copied)
                continue
            combined_attributes = self._combine_attributes(
                earlier_attributes=node_pair.earlier.attributes, later_attributes=node_pair.later.attributes
            )
            combined_relationships = self._combine_relationships(
                earlier_relationships=node_pair.earlier.relationships,
                later_relationships=node_pair.later.relationships,
                node_kind=node_pair.later.kind,
            )
            combined_action = self._combine_actions(earlier=node_pair.earlier.action, later=node_pair.later.action)
            combined_nodes.add(
                EnrichedDiffNode(
                    uuid=node_pair.later.uuid,
                    kind=node_pair.later.kind,
                    label=node_pair.later.label,
                    changed_at=node_pair.later.changed_at or node_pair.earlier.changed_at,
                    action=combined_action,
                    path_identifier=node_pair.later.path_identifier,
                    attributes=combined_attributes,
                    relationships=combined_relationships,
                )
            )
        return combined_nodes

    def _link_child_nodes(self, nodes: Iterable[EnrichedDiffNode]) -> None:
        nodes_by_uuid: dict[str, EnrichedDiffNode] = {n.uuid: n for n in nodes}
        for child_node in nodes_by_uuid.values():
            if child_node.uuid not in self._child_parent_uuid_map:
                continue
            parent_uuid, parent_rel_name = self._child_parent_uuid_map[child_node.uuid]
            parent_node = nodes_by_uuid[parent_uuid]
            parent_rel = child_node.get_relationship(name=parent_rel_name)
            parent_rel.nodes.add(parent_node)

    async def combine(self, earlier_diff: EnrichedDiffRoot, later_diff: EnrichedDiffRoot) -> EnrichedDiffRoot:
        self._initialize(earlier_diff=earlier_diff, later_diff=later_diff)
        filtered_node_pairs = self._filter_nodes_to_keep(earlier_diff=earlier_diff, later_diff=later_diff)
        combined_nodes = self._combine_nodes(node_pairs=filtered_node_pairs)
        self._link_child_nodes(nodes=combined_nodes)
        return EnrichedDiffRoot(
            uuid=str(uuid4()),
            base_branch_name=later_diff.base_branch_name,
            diff_branch_name=later_diff.diff_branch_name,
            from_time=earlier_diff.from_time,
            to_time=later_diff.to_time,
            nodes=combined_nodes,
        )
