from typing import Any

from infrahub.core.query import Query, QueryType
from infrahub.database import InfrahubDatabase

from ..model.path import (
    EnrichedDiffAttribute,
    EnrichedDiffConflict,
    EnrichedDiffNode,
    EnrichedDiffProperty,
    EnrichedDiffRelationship,
    EnrichedDiffs,
    EnrichedDiffSingleRelationship,
    EnrichedNodeCreateRequest,
)


class EnrichedDiffRootsCreateQuery(Query):
    name = "enriched_roots_create"
    type = QueryType.WRITE
    insert_return = False

    def __init__(self, enriched_diffs: EnrichedDiffs, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.enriched_diffs = enriched_diffs

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        self.params = self._build_diff_root_params(enriched_diffs=self.enriched_diffs)
        query = """
UNWIND $diff_root_list AS diff_root_map
WITH diff_root_map
CALL {
    WITH diff_root_map
    MERGE (diff_root:DiffRoot {
        base_branch: diff_root_map.base_branch,
        diff_branch: diff_root_map.diff_branch,
        from_time: diff_root_map.from_time,
        to_time: diff_root_map.to_time,
        uuid: diff_root_map.uuid,
        num_added: diff_root_map.num_added,
        num_updated: diff_root_map.num_updated,
        num_removed: diff_root_map.num_removed,
        num_conflicts: diff_root_map.num_conflicts,
        contains_conflict: diff_root_map.contains_conflict
    })
    SET diff_root.tracking_id = diff_root_map.tracking_id
    RETURN diff_root
}
WITH DISTINCT diff_root AS diff_root
WITH collect(diff_root) AS diff_roots
CALL {
    WITH diff_roots
    WITH diff_roots[0] AS base_diff_node, diff_roots[1] AS branch_diff_node
    MERGE (base_diff_node)-[:DIFF_HAS_PARTNER]-(branch_diff_node)
    SET (base_diff_node).partner_uuid = (branch_diff_node).uuid
    SET (branch_diff_node).partner_uuid = (base_diff_node).uuid
}
        """
        self.add_to_query(query)

    def _build_diff_root_params(self, enriched_diffs: EnrichedDiffs) -> dict[str, Any]:
        diff_root_list: list[dict[str, Any]] = []
        for enriched_diff in (enriched_diffs.base_branch_diff, enriched_diffs.diff_branch_diff):
            diff_root_list.append(
                {
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
            )
        return {"diff_root_list": diff_root_list}


class EnrichedNodeBatchCreateQuery(Query):
    name = "enriched_nodes_create"
    type = QueryType.WRITE
    insert_return = False

    def __init__(self, node_create_batch: list[EnrichedNodeCreateRequest], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.node_create_batch = node_create_batch

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        self.params = self._build_node_batch_params()
        query = """
UNWIND $node_details_list AS node_details
WITH node_details.root_uuid AS root_uuid, node_details.node_map AS node_map
CALL {
    WITH root_uuid, node_map
    MATCH (diff_root {uuid: root_uuid})
    CREATE (diff_root)-[:DIFF_HAS_NODE]->(diff_node:DiffNode)
    SET diff_node = node_map.node_properties
    // -------------------------
    // add node-level conflict
    // -------------------------
    FOREACH (i in CASE WHEN node_map.conflict_params IS NOT NULL THEN [1] ELSE [] END |
        CREATE (diff_node)-[:DIFF_HAS_CONFLICT]->(diff_node_conflict:DiffConflict)
        SET diff_node_conflict = node_map.conflict_params
    )
    // -------------------------
    // add attributes for this node
    // -------------------------
    WITH diff_node, node_map
    CALL {
        WITH diff_node, node_map
        UNWIND node_map.attributes AS node_attribute
        CREATE (diff_node)-[:DIFF_HAS_ATTRIBUTE]->(diff_attribute:DiffAttribute)
        SET diff_attribute = node_attribute.node_properties
        // -------------------------
        // add properties for this attribute
        // -------------------------
        WITH diff_attribute, node_attribute
        UNWIND node_attribute.properties AS attr_property
        CREATE (diff_attribute)-[:DIFF_HAS_PROPERTY]->(diff_attr_prop:DiffProperty)
        SET diff_attr_prop = attr_property.node_properties
        // -------------------------
        // add conflict for this property
        // -------------------------
        FOREACH (i in CASE WHEN attr_property.conflict_params IS NOT NULL THEN [1] ELSE [] END |
            CREATE (diff_attr_prop)-[:DIFF_HAS_CONFLICT]->(diff_attribute_property_conflict:DiffConflict)
            SET diff_attribute_property_conflict = attr_property.conflict_params
        )
    }
    // -------------------------
    // add relationships for this node
    // -------------------------
    WITH diff_node, node_map
    CALL {
        WITH diff_node, node_map
        UNWIND node_map.relationships as node_relationship
        CREATE (diff_node)-[:DIFF_HAS_RELATIONSHIP]->(diff_relationship:DiffRelationship)
        SET diff_relationship = node_relationship.node_properties
        // -------------------------
        // add elements for this relationship group
        // -------------------------
        WITH diff_relationship, node_relationship
        UNWIND node_relationship.relationships as node_single_relationship
        CREATE (diff_relationship)-[:DIFF_HAS_ELEMENT]->(diff_relationship_element:DiffRelationshipElement)
        SET diff_relationship_element = node_single_relationship.node_properties
        // -------------------------
        // add conflict for this relationship element
        // -------------------------
        FOREACH (i in CASE WHEN node_single_relationship.conflict_params IS NOT NULL THEN [1] ELSE [] END |
            CREATE (diff_relationship_element)-[:DIFF_HAS_CONFLICT]->(diff_relationship_conflict:DiffConflict)
            SET diff_relationship_conflict = node_single_relationship.conflict_params
        )
        // -------------------------
        // add properties for this relationship element
        // -------------------------
        WITH diff_relationship_element, node_single_relationship
        UNWIND node_single_relationship.properties as node_relationship_property
        CREATE (diff_relationship_element)-[:DIFF_HAS_PROPERTY]->(diff_relationship_property:DiffProperty)
        SET diff_relationship_property = node_relationship_property.node_properties
        // -------------------------
        // add conflict for this relationship element
        // -------------------------
        FOREACH (i in CASE WHEN node_relationship_property.conflict_params IS NOT NULL THEN [1] ELSE [] END |
            CREATE (diff_relationship_property)-[:DIFF_HAS_CONFLICT]->(diff_relationship_property_conflict:DiffConflict)
            SET diff_relationship_property_conflict = node_relationship_property.conflict_params
        )
    }
}
        """
        self.add_to_query(query)

    def _build_conflict_params(self, enriched_conflict: EnrichedDiffConflict) -> dict[str, Any]:
        return {
            "uuid": enriched_conflict.uuid,
            "base_branch_action": enriched_conflict.base_branch_action.value,
            "base_branch_value": enriched_conflict.base_branch_value,
            "base_branch_changed_at": enriched_conflict.base_branch_changed_at.to_string()
            if enriched_conflict.base_branch_changed_at
            else None,
            "base_branch_label": enriched_conflict.base_branch_label,
            "diff_branch_action": enriched_conflict.diff_branch_action.value,
            "diff_branch_value": enriched_conflict.diff_branch_value,
            "diff_branch_changed_at": enriched_conflict.diff_branch_changed_at.to_string()
            if enriched_conflict.diff_branch_changed_at
            else None,
            "diff_branch_label": enriched_conflict.diff_branch_label,
            "selected_branch": enriched_conflict.selected_branch.value if enriched_conflict.selected_branch else None,
            "resolvable": enriched_conflict.resolvable,
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
                "previous_label": enriched_property.previous_label,
                "new_label": enriched_property.new_label,
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
                "identifier": enriched_relationship.identifier,
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

    def _build_node_batch_params(self) -> dict[str, list[dict[str, Any]]]:
        node_details: list[dict[str, Any]] = []
        for node_create_request in self.node_create_batch:
            node_details.append(
                {
                    "root_uuid": node_create_request.root_uuid,
                    "node_map": self._build_diff_node_params(enriched_node=node_create_request.node),
                }
            )
        return {"node_details_list": node_details}


class EnrichedNodesLinkQuery(Query):
    name = "enriched_nodes_link"
    type = QueryType.WRITE
    insert_return = False

    def __init__(self, enriched_diffs: EnrichedDiffs, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.enriched_diffs = enriched_diffs

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        parent_links_list = []
        for diff_root in (self.enriched_diffs.base_branch_diff, self.enriched_diffs.diff_branch_diff):
            for node in diff_root.nodes:
                parent_links_list.extend(self._build_node_parent_links(enriched_node=node, root_uuid=diff_root.uuid))
        self.params = {"node_links_list": parent_links_list}
        query = """
UNWIND $node_links_list AS node_link_details
WITH
    node_link_details.root_uuid AS root_uuid,
    node_link_details.parent_uuid AS parent_uuid,
    node_link_details.child_uuid AS child_uuid,
    node_link_details.relationship_name AS relationship_name
CALL {
    WITH root_uuid, parent_uuid, child_uuid, relationship_name
    MATCH (diff_root {uuid: root_uuid})
    MATCH (diff_root)-[:DIFF_HAS_NODE]->(parent_node:DiffNode {uuid: parent_uuid})
        -[:DIFF_HAS_RELATIONSHIP]->(diff_rel_group:DiffRelationship {name: relationship_name})
    MATCH (diff_root)-[:DIFF_HAS_NODE]->(child_node:DiffNode {uuid: child_uuid})
    MERGE (diff_rel_group)-[:DIFF_HAS_NODE]->(child_node)
}
        """
        self.add_to_query(query)

    def _build_node_parent_links(self, enriched_node: EnrichedDiffNode, root_uuid: str) -> list[dict[str, str]]:
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
                        "root_uuid": root_uuid,
                    }
                )
                parent_links.extend(self._build_node_parent_links(enriched_node=child_node, root_uuid=root_uuid))
        return parent_links
