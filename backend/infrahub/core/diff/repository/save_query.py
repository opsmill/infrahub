from typing import Any

from infrahub.core.query import Query, QueryType
from infrahub.database import InfrahubDatabase

from ..model.path import (
    EnrichedDiffAttribute,
    EnrichedDiffNode,
    EnrichedDiffProperty,
    EnrichedDiffPropertyConflict,
    EnrichedDiffRelationship,
    EnrichedDiffRoot,
    EnrichedDiffSingleRelationship,
)


class EnrichedDiffSaveQuery(Query):
    name = "enriched_diff_save"
    type = QueryType.WRITE

    def __init__(self, enriched_diff_root: EnrichedDiffRoot, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.enriched_diff_root = enriched_diff_root

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        self.params = self._build_diff_root_params(enriched_diff=self.enriched_diff_root)
        query = """
        MERGE (diff_root:DiffRoot {
            base_branch: $diff_root_props.base_branch,
            diff_branch: $diff_root_props.diff_branch,
            from_time: $diff_root_props.from_time,
            to_time: $diff_root_props.to_time,
            uuid: $diff_root_props.uuid
        })
        WITH diff_root
        UNWIND $node_maps AS node_map
        CREATE (diff_root)-[:DIFF_HAS_NODE]->(diff_node:DiffNode)
        SET diff_node = node_map.node_properties
        WITH diff_root, diff_node, node_map
        UNWIND node_map.attributes AS node_attribute
        CREATE (diff_node)-[:DIFF_HAS_ATTRIBUTE]->(diff_attribute:DiffAttribute)
        SET diff_attribute = node_attribute.node_properties
        """
        self.add_to_query(query=query)
        self.return_labels = ["diff_root.uuid"]

    def _build_diff_conflict_params(self, enriched_conflict: EnrichedDiffPropertyConflict) -> dict[str, Any]:
        if enriched_conflict.selected_branch is None:
            selected_branch = None
        else:
            selected_branch = enriched_conflict.selected_branch.value
        return {
            "node_properties": {
                "uuid": enriched_conflict.uuid,
                "base_branch_action": enriched_conflict.base_branch_action.value,
                "base_branch_value": enriched_conflict.base_branch_value,
                "base_branch_changed_at": enriched_conflict.base_branch_changed_at.to_string(),
                "diff_branch_action": enriched_conflict.diff_branch_action.value,
                "diff_branch_value": enriched_conflict.diff_branch_value,
                "diff_branch_changed_at": enriched_conflict.diff_branch_changed_at.to_string(),
                "selected_branch": selected_branch,
            }
        }

    def _build_diff_property_params(self, enriched_property: EnrichedDiffProperty) -> dict[str, Any]:
        conflict_props = None
        if enriched_property.conflict:
            conflict_props = self._build_diff_conflict_params(enriched_conflict=enriched_property.conflict)
        return {
            "node_properties": {
                "property_type": enriched_property.property_type,
                "changed_at": enriched_property.changed_at,
                "previous_value": enriched_property.previous_value,
                "new_value": enriched_property.new_value,
                "action": enriched_property.action,
            },
            "conflict": conflict_props,
        }

    def _build_diff_attribute_params(self, enriched_attribute: EnrichedDiffAttribute) -> dict[str, Any]:
        property_props = [
            self._build_diff_property_params(enriched_property=prop) for prop in enriched_attribute.properties
        ]
        return {
            "node_properties": {
                "name": enriched_attribute.name,
                "changed_at": enriched_attribute.changed_at.to_string(),
                "action": enriched_attribute.action.value,
            },
            "properties": property_props,
        }

    def _build_diff_single_relationship_params(
        self, enriched_single_relationship: EnrichedDiffSingleRelationship
    ) -> dict[str, Any]:
        property_props = [
            self._build_diff_property_params(enriched_property=prop) for prop in enriched_single_relationship.properties
        ]
        conflict_props = None
        if enriched_single_relationship.conflict:
            conflict_props = self._build_diff_conflict_params(enriched_conflict=enriched_single_relationship.conflict)
        return {
            "node_properties": {
                "changed_at": enriched_single_relationship.changed_at,
                "action": enriched_single_relationship.action,
                "peer_id": enriched_single_relationship.peer_id,
            },
            "conflict": conflict_props,
            "properties": property_props,
        }

    def _build_diff_relationship_params(self, enriched_relationship: EnrichedDiffRelationship) -> dict[str, Any]:
        single_relationship_props = [
            self._build_diff_single_relationship_params(enriched_single_relationship=esr)
            for esr in enriched_relationship.relationships
        ]
        return {
            "node_properties": {
                "name": enriched_relationship.name,
                "changed_at": enriched_relationship.changed_at,
                "action": enriched_relationship.action,
            },
            "relationships": single_relationship_props,
        }

    def _build_diff_node_params(self, enriched_node: EnrichedDiffNode) -> dict[str, Any]:
        attribute_props = [
            self._build_diff_attribute_params(enriched_attribute=attribute) for attribute in enriched_node.attributes
        ]
        relationship_props = [
            self._build_diff_relationship_params(relationship) for relationship in enriched_node.relationships
        ]
        return {
            "node_properties": {
                "uuid": enriched_node.uuid,
                "kind": enriched_node.kind,
                "label": enriched_node.label,
                "changed_at": enriched_node.changed_at.to_string(),
                "action": enriched_node.action.value,
            },
            "attributes": attribute_props,
            "relationships": relationship_props,
        }

    def _build_child_diff_node_params(self, enriched_node: EnrichedDiffNode) -> list[dict[str, Any]]:
        node_maps = []
        for relationship in enriched_node.relationships:
            for child_node in relationship.nodes:
                node_maps.append(self._build_diff_node_params(enriched_node=child_node))
                node_maps.extend(self._build_child_diff_node_params(enriched_node=child_node))
        return node_maps

    def _build_node_parent_links(self, enriched_node: EnrichedDiffNode) -> list[dict[str, str]]:
        if not enriched_node.relationships:
            return []
        parent_links = []
        for relationship in enriched_node.relationships:
            for child_node in relationship.nodes:
                parent_links.append({"parent_uuid": enriched_node.uuid, "child_uuid": child_node.uuid})
                parent_links.extend(self._build_node_parent_links(enriched_node=child_node))
        return parent_links

    def _build_diff_root_params(self, enriched_diff: EnrichedDiffRoot) -> dict[str, Any]:
        params: dict[str, Any] = {}
        params["diff_root_props"] = {
            "base_branch": enriched_diff.base_branch_name,
            "diff_branch": enriched_diff.diff_branch_name,
            "from_time": enriched_diff.from_time.to_string(),
            "to_time": enriched_diff.to_time.to_string(),
            "uuid": enriched_diff.uuid,
        }
        node_maps = []
        node_parent_links = []
        for node in enriched_diff.nodes:
            node_maps.append(self._build_diff_node_params(enriched_node=node))
            node_maps.extend(self._build_child_diff_node_params(enriched_node=node))
            node_parent_links.extend(self._build_node_parent_links(enriched_node=node))
        params["node_maps"] = node_maps
        params["node_parent_links"] = node_parent_links
        return params
