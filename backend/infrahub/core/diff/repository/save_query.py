from typing import Any

from infrahub.core.query import Query, QueryType
from infrahub.database import InfrahubDatabase

from ..model.path import (
    EnrichedDiffAttribute,
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
            uuid: $diff_root_props.uuid
        })
        WITH diff_root
        UNWIND $node_maps AS node_map
        CREATE (diff_root)-[:DIFF_HAS_NODE]->(diff_node:DiffNode)
        SET diff_node = node_map.node_properties

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

            // node relationship properties
            WITH diff_relationship_element, node_single_relationship
            UNWIND node_single_relationship.properties as node_relationship_property
            CREATE (diff_relationship_element)-[:DIFF_HAS_PROPERTY]->(diff_relationship_property:DiffProperty)
            SET diff_relationship_property = node_relationship_property.node_properties
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

    def _build_diff_property_params(self, enriched_property: EnrichedDiffProperty) -> dict[str, Any]:
        return {
            "node_properties": {
                "property_type": enriched_property.property_type,
                "changed_at": enriched_property.changed_at.to_string(),
                "previous_value": enriched_property.previous_value,
                "new_value": enriched_property.new_value,
                "action": enriched_property.action,
            },
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
        return {
            "node_properties": {
                "changed_at": enriched_single_relationship.changed_at.to_string(),
                "action": enriched_single_relationship.action,
                "peer_id": enriched_single_relationship.peer_id,
            },
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
                "changed_at": enriched_relationship.changed_at.to_string(),
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
        }
        node_maps = []
        node_parent_links = []
        for node in enriched_diff.nodes:
            node_maps.append(self._build_diff_node_params(enriched_node=node))
            node_parent_links.extend(self._build_node_parent_links(enriched_node=node))
        params["node_maps"] = node_maps
        params["node_parent_links"] = node_parent_links
        return params
