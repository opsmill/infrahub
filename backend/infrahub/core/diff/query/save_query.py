from typing import Any

from infrahub.core.query import Query, QueryType
from infrahub.database import InfrahubDatabase

from ..model.path import (
    EnrichedDiffAttribute,
    EnrichedDiffConflict,
    EnrichedDiffNode,
    EnrichedDiffProperty,
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
        # ruff: noqa: E501
        query = """
        MERGE (diff_root:DiffRoot {
            base_branch: $diff_root_props.base_branch,
            diff_branch: $diff_root_props.diff_branch,
            from_time: $diff_root_props.from_time,
            to_time: $diff_root_props.to_time,
            uuid: $diff_root_props.uuid,
            num_added: $diff_root_props.num_added,
            num_updated: $diff_root_props.num_updated,
            num_removed: $diff_root_props.num_removed,
            num_conflicts: $diff_root_props.num_conflicts,
            contains_conflict: $diff_root_props.contains_conflict
        })
        SET diff_root.tracking_id = $diff_root_props.tracking_id
        WITH diff_root
        UNWIND $node_maps AS node_map
        CREATE (diff_root)-[:DIFF_HAS_NODE]->(diff_node:DiffNode)
        SET diff_node = node_map.node_properties
        // node conflict
        FOREACH (i in CASE WHEN node_map.conflict_params IS NOT NULL THEN [1] ELSE [] END |
            CREATE (diff_node)-[:DIFF_HAS_CONFLICT]->(diff_node_conflict:DiffConflict)
            SET diff_node_conflict = node_map.conflict_params
        )

        // attributes
        WITH diff_root, diff_node, node_map
        CALL {
            WITH diff_node, node_map
            UNWIND node_map.attributes AS node_attribute
            CREATE (diff_node)-[:DIFF_HAS_ATTRIBUTE]->(diff_attribute:DiffAttribute)
            SET diff_attribute = node_attribute.node_properties

            // node attribute properties
            WITH diff_attribute, node_attribute
            UNWIND node_attribute.properties AS attr_property
            CREATE (diff_attribute)-[:DIFF_HAS_PROPERTY]->(diff_attr_prop:DiffProperty)
            SET diff_attr_prop = attr_property.node_properties
            // attribute property conflict
            FOREACH (i in CASE WHEN attr_property.conflict_params IS NOT NULL THEN [1] ELSE [] END |
                CREATE (diff_attr_prop)-[:DIFF_HAS_CONFLICT]->(diff_attribute_property_conflict:DiffConflict)
                SET diff_attribute_property_conflict = attr_property.conflict_params
            )
        }

        // relationships
        WITH diff_root, diff_node, node_map
        CALL {
            WITH diff_node, node_map
            UNWIND node_map.relationships as node_relationship
            CREATE (diff_node)-[:DIFF_HAS_RELATIONSHIP]->(diff_relationship:DiffRelationship)
            SET diff_relationship = node_relationship.node_properties

            // node single relationships
            WITH diff_relationship, node_relationship
            UNWIND node_relationship.relationships as node_single_relationship
            CREATE (diff_relationship)-[:DIFF_HAS_ELEMENT]->(diff_relationship_element:DiffRelationshipElement)
            SET diff_relationship_element = node_single_relationship.node_properties
            // single relationship conflict
            FOREACH (i in CASE WHEN node_single_relationship.conflict_params IS NOT NULL THEN [1] ELSE [] END |
                CREATE (diff_relationship_element)-[:DIFF_HAS_CONFLICT]->(diff_relationship_conflict:DiffConflict)
                SET diff_relationship_conflict = node_single_relationship.conflict_params
            )

            // node relationship properties
            WITH diff_relationship_element, node_single_relationship
            UNWIND node_single_relationship.properties as node_relationship_property
            CREATE (diff_relationship_element)-[:DIFF_HAS_PROPERTY]->(diff_relationship_property:DiffProperty)
            SET diff_relationship_property = node_relationship_property.node_properties
            // relationship property conflict
            FOREACH (i in CASE WHEN node_relationship_property.conflict_params IS NOT NULL THEN [1] ELSE [] END |
                CREATE (diff_relationship_property)-[:DIFF_HAS_CONFLICT]->(diff_relationship_property_conflict:DiffConflict)
                SET diff_relationship_property_conflict = node_relationship_property.conflict_params
            )
        }
        WITH diff_root
        UNWIND $node_parent_links AS node_parent_link
        CALL {
            WITH diff_root, node_parent_link
            MATCH (diff_root)-[:DIFF_HAS_NODE]->(parent_node:DiffNode {uuid: node_parent_link.parent_uuid})-[:DIFF_HAS_RELATIONSHIP]->(diff_rel_group:DiffRelationship {name: node_parent_link.relationship_name})
            MATCH (diff_root)-[:DIFF_HAS_NODE]->(child_node:DiffNode {uuid: node_parent_link.child_uuid})
            MERGE (diff_rel_group)-[:DIFF_HAS_NODE]->(child_node)
        }
        """
        self.add_to_query(query=query)
        self.return_labels = ["diff_root.uuid"]

    def _build_conflict_params(self, enriched_conflict: EnrichedDiffConflict) -> dict[str, Any]:
        return {
            "uuid": enriched_conflict.uuid,
            "base_branch_action": enriched_conflict.base_branch_action.value,
            "base_branch_value": enriched_conflict.base_branch_value,
            "base_branch_changed_at": enriched_conflict.base_branch_changed_at.to_string()
            if enriched_conflict.base_branch_changed_at
            else None,
            "diff_branch_action": enriched_conflict.diff_branch_action.value,
            "diff_branch_value": enriched_conflict.diff_branch_value,
            "diff_branch_changed_at": enriched_conflict.diff_branch_changed_at.to_string()
            if enriched_conflict.diff_branch_changed_at
            else None,
            "selected_branch": enriched_conflict.selected_branch.value if enriched_conflict.selected_branch else None,
        }

    def _build_diff_property_params(self, enriched_property: EnrichedDiffProperty) -> dict[str, Any]:
        conflict_params = None
        if enriched_property.conflict:
            conflict_params = self._build_conflict_params(enriched_conflict=enriched_property.conflict)
        return {
            "node_properties": {
                "property_type": enriched_property.property_type.value,
                "changed_at": enriched_property.changed_at.to_string(),
                "previous_value": enriched_property.previous_value,
                "new_value": enriched_property.new_value,
                "action": enriched_property.action,
                "path_identifier": enriched_property.path_identifier,
            },
            "conflict_params": conflict_params,
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
                "path_identifier": enriched_attribute.path_identifier,
                "num_added": enriched_attribute.num_added,
                "num_updated": enriched_attribute.num_updated,
                "num_removed": enriched_attribute.num_removed,
                "num_conflicts": enriched_attribute.num_conflicts,
                "contains_conflict": enriched_attribute.contains_conflict,
            },
            "properties": property_props,
        }

    def _build_diff_single_relationship_params(
        self, enriched_single_relationship: EnrichedDiffSingleRelationship
    ) -> dict[str, Any]:
        property_props = [
            self._build_diff_property_params(enriched_property=prop) for prop in enriched_single_relationship.properties
        ]
        conflict_params = None
        if enriched_single_relationship.conflict:
            conflict_params = self._build_conflict_params(enriched_conflict=enriched_single_relationship.conflict)
        return {
            "node_properties": {
                "changed_at": enriched_single_relationship.changed_at.to_string(),
                "action": enriched_single_relationship.action,
                "peer_id": enriched_single_relationship.peer_id,
                "peer_label": enriched_single_relationship.peer_label,
                "path_identifier": enriched_single_relationship.path_identifier,
                "num_added": enriched_single_relationship.num_added,
                "num_updated": enriched_single_relationship.num_updated,
                "num_removed": enriched_single_relationship.num_removed,
                "num_conflicts": enriched_single_relationship.num_conflicts,
                "contains_conflict": enriched_single_relationship.contains_conflict,
            },
            "conflict_params": conflict_params,
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
                "label": enriched_relationship.label,
                "cardinality": enriched_relationship.cardinality.value,
                "changed_at": enriched_relationship.changed_at.to_string()
                if enriched_relationship.changed_at
                else None,
                "action": enriched_relationship.action,
                "path_identifier": enriched_relationship.path_identifier,
                "num_added": enriched_relationship.num_added,
                "num_updated": enriched_relationship.num_updated,
                "num_removed": enriched_relationship.num_removed,
                "num_conflicts": enriched_relationship.num_conflicts,
                "contains_conflict": enriched_relationship.contains_conflict,
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
        conflict_params = None
        if enriched_node.conflict:
            conflict_params = self._build_conflict_params(enriched_conflict=enriched_node.conflict)
        return {
            "node_properties": {
                "uuid": enriched_node.uuid,
                "kind": enriched_node.kind,
                "label": enriched_node.label,
                "changed_at": enriched_node.changed_at.to_string() if enriched_node.changed_at else None,
                "action": enriched_node.action.value,
                "path_identifier": enriched_node.path_identifier,
                "num_added": enriched_node.num_added,
                "num_updated": enriched_node.num_updated,
                "num_removed": enriched_node.num_removed,
                "num_conflicts": enriched_node.num_conflicts,
                "contains_conflict": enriched_node.contains_conflict,
            },
            "conflict_params": conflict_params,
            "attributes": attribute_props,
            "relationships": relationship_props,
        }

    def _build_node_parent_links(self, enriched_node: EnrichedDiffNode) -> list[dict[str, str]]:
        if not enriched_node.relationships:
            return []
        parent_links = []
        for relationship in enriched_node.relationships:
            for child_node in relationship.nodes:
                parent_links.append(
                    {
                        "parent_uuid": enriched_node.uuid,
                        "relationship_name": relationship.name,
                        "child_uuid": child_node.uuid,
                    }
                )
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
            "tracking_id": enriched_diff.tracking_id.serialize() if enriched_diff.tracking_id else None,
            "num_added": enriched_diff.num_added,
            "num_updated": enriched_diff.num_updated,
            "num_removed": enriched_diff.num_removed,
            "num_conflicts": enriched_diff.num_conflicts,
            "contains_conflict": enriched_diff.contains_conflict,
        }
        node_maps = []
        node_parent_links = []
        for node in enriched_diff.nodes:
            node_maps.append(self._build_diff_node_params(enriched_node=node))
            node_parent_links.extend(self._build_node_parent_links(enriched_node=node))
        params["node_maps"] = node_maps
        params["node_parent_links"] = node_parent_links
        return params
