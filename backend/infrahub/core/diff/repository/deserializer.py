from neo4j.graph import Node as Neo4jNode
from neo4j.graph import Path as Neo4jPath

from infrahub.core.constants import DiffAction, RelationshipCardinality
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.query import QueryResult
from infrahub.core.timestamp import Timestamp

from ..model.path import (
    ConflictSelection,
    EnrichedDiffAttribute,
    EnrichedDiffConflict,
    EnrichedDiffNode,
    EnrichedDiffProperty,
    EnrichedDiffRelationship,
    EnrichedDiffRoot,
    EnrichedDiffRootMetadata,
    EnrichedDiffSingleRelationship,
    deserialize_tracking_id,
)
from ..parent_node_adder import DiffParentNodeAdder, ParentNodeAddRequest


class EnrichedDiffDeserializer:
    def __init__(self, parent_adder: DiffParentNodeAdder) -> None:
        self.parent_adder = parent_adder
        self._diff_root_map: dict[str, EnrichedDiffRoot] = {}
        self._diff_node_map: dict[tuple[str, str], EnrichedDiffNode] = {}
        self._diff_node_attr_map: dict[tuple[str, str, str], EnrichedDiffAttribute] = {}
        self._diff_node_rel_group_map: dict[tuple[str, str, str], EnrichedDiffRelationship] = {}
        self._diff_node_rel_element_map: dict[tuple[str, str, str, str], EnrichedDiffSingleRelationship] = {}
        self._diff_prop_map: dict[tuple[str, str, str, str] | tuple[str, str, str, str, str], EnrichedDiffProperty] = {}
        # {EnrichedDiffRoot: [(node_uuid, parents_path: Neo4jPath), ...]}
        self._parents_path_map: dict[EnrichedDiffRoot, list[tuple[str, Neo4jPath]]] = {}

    def initialize(self) -> None:
        self._diff_root_map = {}
        self._diff_node_map = {}
        self._diff_node_attr_map = {}
        self._diff_node_rel_group_map = {}
        self._diff_node_rel_element_map = {}
        self._diff_prop_map = {}
        self._parents_path_map = {}

    def _track_parents_path(self, enriched_root: EnrichedDiffRoot, node_uuid: str, parents_path: Neo4jPath) -> None:
        if enriched_root not in self._parents_path_map:
            self._parents_path_map[enriched_root] = []
        self._parents_path_map[enriched_root].append((node_uuid, parents_path))

    async def read_result(self, result: QueryResult, include_parents: bool) -> None:
        enriched_root = self._deserialize_diff_root(root_node=result.get_node("diff_root"))
        node_node = result.get(label="diff_node")
        if not isinstance(node_node, Neo4jNode):
            return
        enriched_node = self._deserialize_diff_node(node_node=node_node, enriched_root=enriched_root)

        if include_parents:
            parents_path = result.get("parents_path")
            if parents_path and isinstance(parents_path, Neo4jPath):
                self._track_parents_path(
                    enriched_root=enriched_root, node_uuid=enriched_node.uuid, parents_path=parents_path
                )

        node_conflict_node = result.get(label="diff_node_conflict")
        if isinstance(node_conflict_node, Neo4jNode) and not enriched_node.conflict:
            conflict = self.deserialize_conflict(diff_conflict_node=node_conflict_node)
            enriched_node.conflict = conflict
        self._deserialize_attributes(result=result, enriched_root=enriched_root, enriched_node=enriched_node)
        self._deserialize_relationships(result=result, enriched_root=enriched_root, enriched_node=enriched_node)

    async def deserialize(self, include_parents: bool = True) -> list[EnrichedDiffRoot]:
        if include_parents:
            self._deserialize_parents()

        return list(self._diff_root_map.values())

    def _deserialize_attributes(
        self, result: QueryResult, enriched_root: EnrichedDiffRoot, enriched_node: EnrichedDiffNode
    ) -> None:
        for attribute_result in result.get_nested_node_collection("diff_attributes"):
            diff_attr_node, diff_attr_property_node, diff_attr_property_conflict = attribute_result
            if diff_attr_node is None or diff_attr_property_node is None:
                continue
            enriched_attribute = self._deserialize_diff_attr(
                diff_attr_node=diff_attr_node, enriched_root=enriched_root, enriched_node=enriched_node
            )
            enriched_property = self._deserialize_diff_attr_property(
                diff_attr_property_node=diff_attr_property_node,
                enriched_attr=enriched_attribute,
                enriched_node=enriched_node,
                enriched_root=enriched_root,
            )
            if diff_attr_property_conflict:
                conflict = self.deserialize_conflict(diff_conflict_node=diff_attr_property_conflict)
                enriched_property.conflict = conflict

    def _deserialize_relationships(
        self, result: QueryResult, enriched_root: EnrichedDiffRoot, enriched_node: EnrichedDiffNode
    ) -> None:
        for relationship_result in result.get_nested_node_collection("diff_relationships"):
            group_node, element_node, element_conflict, property_node, property_conflict = relationship_result
            enriched_relationship_group = None
            if group_node:
                enriched_relationship_group = self._deserialize_diff_relationship_group(
                    relationship_group_node=group_node, enriched_root=enriched_root, enriched_node=enriched_node
                )
            if element_node is None or property_node is None or enriched_relationship_group is None:
                continue

            enriched_relationship_element = self._deserialize_diff_relationship_element(
                relationship_element_node=element_node,
                enriched_relationship_group=enriched_relationship_group,
                enriched_node=enriched_node,
                enriched_root=enriched_root,
            )
            if element_conflict and not enriched_relationship_element.conflict:
                conflict = self.deserialize_conflict(diff_conflict_node=element_conflict)
                enriched_relationship_element.conflict = conflict
            element_property = self._deserialize_diff_relationship_element_property(
                relationship_element_property_node=property_node,
                enriched_relationship_element=enriched_relationship_element,
                enriched_relationship_group=enriched_relationship_group,
                enriched_node=enriched_node,
                enriched_root=enriched_root,
            )
            if property_conflict:
                conflict = self.deserialize_conflict(diff_conflict_node=property_conflict)
                element_property.conflict = conflict

    def _deserialize_parents(self) -> None:
        for enriched_root, node_path_tuples in self._parents_path_map.items():
            self.parent_adder.initialize(enriched_diff_root=enriched_root)
            for node_uuid, parents_path in node_path_tuples:
                # Remove the node itself from the path
                parents_path_slice = parents_path.nodes[1:]

                # TODO Ensure the list is even
                current_node_uuid = node_uuid
                for rel, parent in zip(parents_path_slice[::2], parents_path_slice[1::2], strict=False):
                    parent_request = ParentNodeAddRequest(
                        node_id=current_node_uuid,
                        parent_id=parent.get("uuid"),
                        parent_kind=parent.get("kind"),
                        parent_label=parent.get("label"),
                        parent_rel_name=rel.get("name"),
                        parent_rel_identifier=rel.get("identifier"),
                        parent_rel_cardinality=RelationshipCardinality(rel.get("cardinality")),
                        parent_rel_label=rel.get("label"),
                    )
                    self.parent_adder.add_parent(parent_request=parent_request)
                    current_node_uuid = parent.get("uuid")

    @classmethod
    def _get_str_or_none_property_value(cls, node: Neo4jNode, property_name: str) -> str | None:
        value_raw = node.get(property_name)
        return str(value_raw) if value_raw is not None else None

    def _deserialize_diff_root(self, root_node: Neo4jNode) -> EnrichedDiffRoot:
        root_uuid = str(root_node.get("uuid"))
        if root_uuid in self._diff_root_map:
            return self._diff_root_map[root_uuid]
        root_empty = self.build_diff_root_metadata(root_node=root_node)
        enriched_root = EnrichedDiffRoot.from_root_metadata(empty_root=root_empty)
        self._diff_root_map[root_uuid] = enriched_root
        return enriched_root

    @classmethod
    def build_diff_root_metadata(cls, root_node: Neo4jNode) -> EnrichedDiffRootMetadata:
        from_time = Timestamp(str(root_node.get("from_time")))
        to_time = Timestamp(str(root_node.get("to_time")))
        partner_uuid = cls._get_str_or_none_property_value(node=root_node, property_name="partner_uuid")
        tracking_id_str = str(root_node.get("tracking_id"))
        tracking_id = deserialize_tracking_id(tracking_id_str=tracking_id_str)
        return EnrichedDiffRootMetadata(
            base_branch_name=str(root_node.get("base_branch")),
            diff_branch_name=str(root_node.get("diff_branch")),
            from_time=from_time,
            to_time=to_time,
            uuid=str(root_node.get("uuid")),
            partner_uuid=partner_uuid,
            tracking_id=tracking_id,
            num_added=int(root_node.get("num_added", 0)),
            num_updated=int(root_node.get("num_updated", 0)),
            num_removed=int(root_node.get("num_removed", 0)),
            num_conflicts=int(root_node.get("num_conflicts", 0)),
            contains_conflict=str(root_node.get("contains_conflict")).lower() == "true",
            exists_on_database=True,
        )

    def _deserialize_diff_node(self, node_node: Neo4jNode, enriched_root: EnrichedDiffRoot) -> EnrichedDiffNode:
        node_uuid = str(node_node.get("uuid"))
        node_key = (enriched_root.uuid, node_uuid)
        if node_key in self._diff_node_map:
            return self._diff_node_map[node_key]

        timestamp_str = self._get_str_or_none_property_value(node=node_node, property_name="changed_at")
        enriched_node = EnrichedDiffNode(
            uuid=node_uuid,
            kind=str(node_node.get("kind")),
            label=str(node_node.get("label")),
            changed_at=Timestamp(timestamp_str) if timestamp_str else None,
            action=DiffAction(str(node_node.get("action"))),
            path_identifier=str(node_node.get("path_identifier")),
            num_added=int(node_node.get("num_added", 0)),
            num_updated=int(node_node.get("num_updated", 0)),
            num_removed=int(node_node.get("num_removed", 0)),
            num_conflicts=int(node_node.get("num_conflicts", 0)),
            contains_conflict=str(node_node.get("contains_conflict")).lower() == "true",
        )
        self._diff_node_map[node_key] = enriched_node
        enriched_root.nodes.add(enriched_node)
        return enriched_node

    def _deserialize_diff_attr(
        self, diff_attr_node: Neo4jNode, enriched_root: EnrichedDiffRoot, enriched_node: EnrichedDiffNode
    ) -> EnrichedDiffAttribute:
        attr_name = str(diff_attr_node.get("name"))
        attr_key = (enriched_root.uuid, enriched_node.uuid, attr_name)
        if attr_key in self._diff_node_attr_map:
            return self._diff_node_attr_map[attr_key]

        enriched_attr = EnrichedDiffAttribute(
            name=str(diff_attr_node.get("name")),
            changed_at=Timestamp(str(diff_attr_node.get("changed_at"))),
            path_identifier=str(diff_attr_node.get("path_identifier")),
            action=DiffAction(str(diff_attr_node.get("action"))),
            num_added=int(diff_attr_node.get("num_added", 0)),
            num_updated=int(diff_attr_node.get("num_updated", 0)),
            num_removed=int(diff_attr_node.get("num_removed", 0)),
            num_conflicts=int(diff_attr_node.get("num_conflicts", 0)),
            contains_conflict=str(diff_attr_node.get("contains_conflict")).lower() == "true",
        )
        self._diff_node_attr_map[attr_key] = enriched_attr
        enriched_node.attributes.add(enriched_attr)
        return enriched_attr

    def _deserialize_diff_relationship_group(
        self, relationship_group_node: Neo4jNode, enriched_root: EnrichedDiffRoot, enriched_node: EnrichedDiffNode
    ) -> EnrichedDiffRelationship:
        diff_rel_name = str(relationship_group_node.get("name"))
        rel_key = (enriched_root.uuid, enriched_node.uuid, diff_rel_name)
        if rel_key in self._diff_node_rel_group_map:
            return self._diff_node_rel_group_map[rel_key]

        timestamp_str = relationship_group_node.get("changed_at")
        enriched_relationship = EnrichedDiffRelationship(
            name=relationship_group_node.get("name"),
            identifier=relationship_group_node.get("identifier"),
            label=relationship_group_node.get("label"),
            cardinality=RelationshipCardinality(relationship_group_node.get("cardinality")),
            changed_at=Timestamp(timestamp_str) if timestamp_str else None,
            action=DiffAction(str(relationship_group_node.get("action"))),
            path_identifier=str(relationship_group_node.get("path_identifier")),
            num_added=int(relationship_group_node.get("num_added", 0)),
            num_conflicts=int(relationship_group_node.get("num_conflicts", 0)),
            num_removed=int(relationship_group_node.get("num_removed", 0)),
            num_updated=int(relationship_group_node.get("num_updated", 0)),
            contains_conflict=str(relationship_group_node.get("contains_conflict")).lower() == "true",
        )

        self._diff_node_rel_group_map[rel_key] = enriched_relationship
        enriched_node.relationships.add(enriched_relationship)
        return enriched_relationship

    def _deserialize_diff_relationship_element(
        self,
        relationship_element_node: Neo4jNode,
        enriched_relationship_group: EnrichedDiffRelationship,
        enriched_node: EnrichedDiffNode,
        enriched_root: EnrichedDiffRoot,
    ) -> EnrichedDiffSingleRelationship:
        diff_element_peer_id = str(relationship_element_node.get("peer_id"))
        rel_element_key = (
            enriched_root.uuid,
            enriched_node.uuid,
            enriched_relationship_group.name,
            diff_element_peer_id,
        )
        if rel_element_key in self._diff_node_rel_element_map:
            return self._diff_node_rel_element_map[rel_element_key]

        peer_label = self._get_str_or_none_property_value(node=relationship_element_node, property_name="peer_label")
        enriched_rel_element = EnrichedDiffSingleRelationship(
            changed_at=Timestamp(str(relationship_element_node.get("changed_at"))),
            action=DiffAction(str(relationship_element_node.get("action"))),
            peer_id=diff_element_peer_id,
            peer_label=peer_label,
            path_identifier=str(relationship_element_node.get("path_identifier")),
            num_added=int(relationship_element_node.get("num_added", 0)),
            num_updated=int(relationship_element_node.get("num_updated", 0)),
            num_removed=int(relationship_element_node.get("num_removed", 0)),
            num_conflicts=int(relationship_element_node.get("num_conflicts", 0)),
            contains_conflict=str(relationship_element_node.get("contains_conflict")).lower() == "true",
        )
        enriched_relationship_group.relationships.add(enriched_rel_element)
        self._diff_node_rel_element_map[rel_element_key] = enriched_rel_element
        return enriched_rel_element

    def _property_node_to_enriched_property(self, property_node: Neo4jNode) -> EnrichedDiffProperty:
        previous_value = self._get_str_or_none_property_value(node=property_node, property_name="previous_value")
        new_value = self._get_str_or_none_property_value(node=property_node, property_name="new_value")
        previous_label = self._get_str_or_none_property_value(node=property_node, property_name="previous_label")
        new_label = self._get_str_or_none_property_value(node=property_node, property_name="new_label")
        return EnrichedDiffProperty(
            property_type=DatabaseEdgeType(str(property_node.get("property_type"))),
            changed_at=Timestamp(str(property_node.get("changed_at"))),
            previous_value=previous_value,
            new_value=new_value,
            previous_label=previous_label,
            new_label=new_label,
            action=DiffAction(str(property_node.get("action"))),
            path_identifier=str(property_node.get("path_identifier")),
        )

    def _deserialize_diff_attr_property(
        self,
        diff_attr_property_node: Neo4jNode,
        enriched_attr: EnrichedDiffAttribute,
        enriched_node: EnrichedDiffNode,
        enriched_root: EnrichedDiffRoot,
    ) -> EnrichedDiffProperty:
        diff_prop_type = str(diff_attr_property_node.get("property_type"))
        attr_property_key = (enriched_root.uuid, enriched_node.uuid, enriched_attr.name, diff_prop_type)
        if attr_property_key in self._diff_prop_map:
            return self._diff_prop_map[attr_property_key]

        enriched_property = self._property_node_to_enriched_property(property_node=diff_attr_property_node)
        enriched_attr.properties.add(enriched_property)
        self._diff_prop_map[attr_property_key] = enriched_property
        return enriched_property

    def _deserialize_diff_relationship_element_property(
        self,
        relationship_element_property_node: Neo4jNode,
        enriched_relationship_element: EnrichedDiffSingleRelationship,
        enriched_relationship_group: EnrichedDiffRelationship,
        enriched_node: EnrichedDiffNode,
        enriched_root: EnrichedDiffRoot,
    ) -> EnrichedDiffProperty:
        diff_prop_type = str(relationship_element_property_node.get("property_type"))
        rel_property_key = (
            enriched_root.uuid,
            enriched_node.uuid,
            enriched_relationship_group.name,
            enriched_relationship_element.peer_id,
            diff_prop_type,
        )
        if rel_property_key in self._diff_prop_map:
            return self._diff_prop_map[rel_property_key]

        enriched_property = self._property_node_to_enriched_property(property_node=relationship_element_property_node)
        self._diff_prop_map[rel_property_key] = enriched_property
        enriched_relationship_element.properties.add(enriched_property)
        return enriched_property

    def deserialize_conflict(self, diff_conflict_node: Neo4jNode) -> EnrichedDiffConflict:
        base_branch_value = self._get_str_or_none_property_value(
            node=diff_conflict_node, property_name="base_branch_value"
        )
        diff_branch_value = self._get_str_or_none_property_value(
            node=diff_conflict_node, property_name="diff_branch_value"
        )
        base_branch_label = self._get_str_or_none_property_value(
            node=diff_conflict_node, property_name="base_branch_label"
        )
        diff_branch_label = self._get_str_or_none_property_value(
            node=diff_conflict_node, property_name="diff_branch_label"
        )
        base_timestamp_str = self._get_str_or_none_property_value(
            node=diff_conflict_node, property_name="base_branch_changed_at"
        )
        diff_timestamp_str = self._get_str_or_none_property_value(
            node=diff_conflict_node, property_name="diff_branch_changed_at"
        )
        selected_branch = self._get_str_or_none_property_value(node=diff_conflict_node, property_name="selected_branch")
        resolvable = str(diff_conflict_node.get("resolvable")).lower() == "true"
        return EnrichedDiffConflict(
            uuid=str(diff_conflict_node.get("uuid")),
            base_branch_action=DiffAction(str(diff_conflict_node.get("base_branch_action"))),
            base_branch_value=base_branch_value,
            base_branch_changed_at=Timestamp(base_timestamp_str) if base_timestamp_str else None,
            base_branch_label=base_branch_label,
            diff_branch_action=DiffAction(str(diff_conflict_node.get("diff_branch_action"))),
            diff_branch_value=diff_branch_value,
            diff_branch_label=diff_branch_label,
            diff_branch_changed_at=Timestamp(diff_timestamp_str) if diff_timestamp_str else None,
            selected_branch=ConflictSelection(selected_branch) if selected_branch else None,
            resolvable=resolvable,
        )
