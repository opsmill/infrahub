import json
from typing import Any, Iterable

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
    EnrichedDiffsMetadata,
    EnrichedNodeCreateRequest,
)


class EnrichedDiffRootsUpsertQuery(Query):
    name = "enriched_roots_create"
    type = QueryType.WRITE
    insert_return = False

    def __init__(self, enriched_diffs: EnrichedDiffs | EnrichedDiffsMetadata, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.enriched_diffs = enriched_diffs

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = self._build_diff_root_params(enriched_diffs=self.enriched_diffs)
        query = """
UNWIND $diff_root_list AS diff_root_map
WITH diff_root_map
CALL {
    WITH diff_root_map
    MERGE (diff_root:DiffRoot {uuid: diff_root_map.uuid})
    SET diff_root.base_branch = diff_root_map.base_branch
    SET diff_root.diff_branch = diff_root_map.diff_branch
    SET diff_root.from_time = diff_root_map.from_time
    SET diff_root.to_time = diff_root_map.to_time
    SET diff_root.tracking_id = diff_root_map.tracking_id
    RETURN diff_root
}
WITH DISTINCT diff_root AS diff_root
WITH collect(diff_root) AS diff_roots
WHERE SIZE(diff_roots) = 2
CALL {
    WITH diff_roots
    WITH diff_roots[0] AS base_diff_node, diff_roots[1] AS branch_diff_node
    MERGE (base_diff_node)-[:DIFF_HAS_PARTNER]-(branch_diff_node)
    SET (base_diff_node).partner_uuid = (branch_diff_node).uuid
    SET (branch_diff_node).partner_uuid = (base_diff_node).uuid
}
        """
        self.add_to_query(query)

    def _build_diff_root_params(self, enriched_diffs: EnrichedDiffs | EnrichedDiffsMetadata) -> dict[str, Any]:
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

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = self._build_node_batch_params()
        query = """
UNWIND $node_details_list AS node_details
WITH
    node_details.root_uuid AS root_uuid,
    node_details.node_map AS node_map,
    toString(node_details.node_map.node_properties.uuid) AS node_uuid
MERGE (diff_root:DiffRoot {uuid: root_uuid})
MERGE (diff_root)-[:DIFF_HAS_NODE]->(diff_node:DiffNode {uuid: node_uuid})
WITH root_uuid, node_map, diff_node, (node_map.conflict_params IS NOT NULL) AS has_node_conflict
SET
    diff_node.kind = node_map.node_properties.kind,
    diff_node.label = node_map.node_properties.label,
    diff_node.db_labels = node_map.node_properties.db_labels,
    diff_node.changed_at = node_map.node_properties.changed_at,
    diff_node.action = node_map.node_properties.action,
    diff_node.path_identifier = node_map.node_properties.path_identifier
WITH root_uuid, node_map, diff_node, has_node_conflict
CALL {
    // -------------------------
    // delete parent-child relationships for included nodes, they will be added in EnrichedNodesLinkQuery
    // -------------------------
    WITH diff_node
    MATCH (diff_node)-[:DIFF_HAS_RELATIONSHIP]->(:DiffRelationship)-[parent_rel:DIFF_HAS_NODE]->(:DiffNode)
    DELETE parent_rel
}
OPTIONAL MATCH (diff_node)-[:DIFF_HAS_CONFLICT]->(current_node_conflict:DiffConflict)
CALL {
    // -------------------------
    // create a node-level conflict, if necessary
    // -------------------------
    WITH diff_node, current_node_conflict, has_node_conflict
    WITH diff_node, current_node_conflict, has_node_conflict
    WHERE current_node_conflict IS NULL AND has_node_conflict = TRUE
    CREATE (diff_node)-[:DIFF_HAS_CONFLICT]->(:DiffConflict)
}
CALL {
    // -------------------------
    // delete a node-level conflict, if necessary
    // -------------------------
    WITH current_node_conflict, has_node_conflict
    WITH current_node_conflict, has_node_conflict
    WHERE current_node_conflict IS NOT NULL AND has_node_conflict = FALSE
    DETACH DELETE current_node_conflict
}
WITH root_uuid, node_map, diff_node, has_node_conflict, node_map.conflict_params AS node_conflict_params
CALL {
    // -------------------------
    // set the properties of the node-level conflict, if necessary
    // -------------------------
    WITH diff_node, has_node_conflict, node_conflict_params
    WITH diff_node, has_node_conflict, node_conflict_params
    WHERE has_node_conflict = TRUE
    OPTIONAL MATCH (diff_node)-[:DIFF_HAS_CONFLICT]->(node_conflict:DiffConflict)
    SET node_conflict = node_conflict_params
}
CALL {
    // -------------------------
    // remove stale attributes for this node
    // -------------------------
    WITH diff_node, node_map
    CALL {
        WITH diff_node, node_map
        WITH diff_node, %(attr_name_list_comp)s AS attr_names
        OPTIONAL MATCH (diff_node)-[:DIFF_HAS_ATTRIBUTE]->(attr_to_delete:DiffAttribute)
        WHERE NOT (attr_to_delete.name IN attr_names)
        OPTIONAL MATCH (attr_to_delete)-[*..6]->(next_to_delete)
        DETACH DELETE next_to_delete
        DETACH DELETE attr_to_delete
    }
    // -------------------------
    // add attributes for this node
    // -------------------------
    UNWIND node_map.attributes AS node_attribute
    MERGE (diff_node)-[:DIFF_HAS_ATTRIBUTE]->(diff_attribute:DiffAttribute {name: node_attribute.node_properties.name})
    SET diff_attribute = node_attribute.node_properties
    // -------------------------
    // add properties for this attribute
    // -------------------------
    WITH diff_attribute, node_attribute
    // -------------------------
    // remove stale properties for this attribute
    // -------------------------
    CALL {
        WITH diff_attribute, node_attribute
        WITH diff_attribute, %(attr_props_list_comp)s AS prop_types
        OPTIONAL MATCH (diff_attribute)-[:DIFF_HAS_PROPERTY]->(prop_to_delete:DiffProperty)
        WHERE NOT (prop_to_delete.property_type IN prop_types)
        OPTIONAL MATCH (prop_to_delete)-[*..4]->(next_to_delete)
        DETACH DELETE next_to_delete
        DETACH DELETE prop_to_delete
    }
    UNWIND node_attribute.properties AS attr_property
    MERGE (diff_attribute)-[:DIFF_HAS_PROPERTY]->(diff_attr_prop:DiffProperty {property_type: attr_property.node_properties.property_type})
    SET diff_attr_prop = attr_property.node_properties
    // -------------------------
    // add/remove conflict for this property
    // -------------------------
    WITH diff_attr_prop, attr_property
    OPTIONAL MATCH (diff_attr_prop)-[:DIFF_HAS_CONFLICT]->(current_attr_prop_conflict:DiffConflict)
    WITH diff_attr_prop, attr_property, current_attr_prop_conflict, (attr_property.conflict_params IS NOT NULL) AS has_prop_conflict
    FOREACH (i in CASE WHEN has_prop_conflict = FALSE THEN [1] ELSE [] END |
        DETACH DELETE current_attr_prop_conflict
    )
    FOREACH (i in CASE WHEN has_prop_conflict = TRUE THEN [1] ELSE [] END |
        MERGE (diff_attr_prop)-[:DIFF_HAS_CONFLICT]->(diff_attr_prop_conflict:DiffConflict)
        SET diff_attr_prop_conflict = attr_property.conflict_params
    )
}
// -------------------------
// remove stale relationships for this node
// -------------------------
CALL {
    WITH diff_node, node_map
    WITH diff_node, %(rel_name_list_comp)s AS rel_names
    OPTIONAL MATCH (diff_node)-[:DIFF_HAS_RELATIONSHIP]->(rel_to_delete:DiffRelationship)
    WHERE NOT (rel_to_delete.name IN rel_names)
    OPTIONAL MATCH (rel_to_delete)-[*..8]->(next_to_delete)
    DETACH DELETE next_to_delete
    DETACH DELETE rel_to_delete
}
// -------------------------
// add relationships for this node
// -------------------------
WITH diff_node, node_map
UNWIND node_map.relationships as node_relationship
MERGE (diff_node)-[:DIFF_HAS_RELATIONSHIP]->(diff_relationship:DiffRelationship {name: node_relationship.node_properties.name})
SET diff_relationship = node_relationship.node_properties
// -------------------------
// remove stale elements for this relationship group
// -------------------------
WITH diff_relationship, node_relationship
CALL {
    WITH diff_relationship, node_relationship
    WITH diff_relationship, %(rel_peers_list_comp)s AS rel_peers
    OPTIONAL MATCH (diff_relationship)-[:DIFF_HAS_ELEMENT]->(element_to_delete:DiffRelationshipElement)
    WHERE NOT (element_to_delete.peer_id IN rel_peers)
    OPTIONAL MATCH (element_to_delete)-[*..6]->(next_to_delete)
    DETACH DELETE next_to_delete
    DETACH DELETE element_to_delete
}
// -------------------------
// add elements for this relationship group
// -------------------------
WITH diff_relationship, node_relationship
UNWIND node_relationship.relationships as node_single_relationship
MERGE (diff_relationship)-[:DIFF_HAS_ELEMENT]
    ->(diff_relationship_element:DiffRelationshipElement {peer_id: node_single_relationship.node_properties.peer_id})
SET diff_relationship_element = node_single_relationship.node_properties
// -------------------------
// add/remove conflict for this relationship element
// -------------------------
WITH diff_relationship_element, node_single_relationship
OPTIONAL MATCH (diff_relationship_element)-[:DIFF_HAS_CONFLICT]->(current_element_conflict:DiffConflict)
WITH diff_relationship_element, node_single_relationship, current_element_conflict,
    (node_single_relationship.conflict_params IS NOT NULL) AS has_element_conflict
FOREACH (i in CASE WHEN has_element_conflict = FALSE THEN [1] ELSE [] END |
    DETACH DELETE current_element_conflict
)
FOREACH (i in CASE WHEN has_element_conflict = TRUE THEN [1] ELSE [] END |
    MERGE (diff_relationship_element)-[:DIFF_HAS_CONFLICT]->(element_conflict:DiffConflict)
    SET element_conflict = node_single_relationship.conflict_params
)
// -------------------------
// remove stale properties for this relationship element
// -------------------------
WITH diff_relationship_element, node_single_relationship
CALL {
    WITH diff_relationship_element, node_single_relationship
    WITH diff_relationship_element, %(element_props_list_comp)s AS element_props
    OPTIONAL MATCH (diff_relationship_element)-[:DIFF_HAS_PROPERTY]->(property_to_delete:DiffProperty)
    WHERE NOT (property_to_delete.property_type IN element_props)
    OPTIONAL MATCH (property_to_delete)-[*..4]->(next_to_delete)
    DETACH DELETE next_to_delete
    DETACH DELETE property_to_delete
}
// -------------------------
// add properties for this relationship element
// -------------------------
WITH diff_relationship_element, node_single_relationship
UNWIND node_single_relationship.properties as node_relationship_property
MERGE (diff_relationship_element)-[:DIFF_HAS_PROPERTY]
    ->(diff_relationship_property:DiffProperty {property_type: node_relationship_property.node_properties.property_type})
SET diff_relationship_property = node_relationship_property.node_properties
// -------------------------
// add conflict for this relationship element
// -------------------------
WITH diff_relationship_property, node_relationship_property
OPTIONAL MATCH (diff_relationship_property)-[:DIFF_HAS_CONFLICT]->(diff_relationship_property_conflict:DiffConflict)
WITH diff_relationship_property, node_relationship_property, diff_relationship_property_conflict,
    (node_relationship_property.conflict_params IS NOT NULL) AS has_property_conflict
FOREACH (i in CASE WHEN has_property_conflict = FALSE THEN [1] ELSE [] END |
    DETACH DELETE diff_relationship_property_conflict
)
FOREACH (i in CASE WHEN has_property_conflict = TRUE THEN [1] ELSE [] END |
    MERGE (diff_relationship_property)-[:DIFF_HAS_CONFLICT]->(property_conflict:DiffConflict)
    SET property_conflict = node_relationship_property.conflict_params
)
        """ % {
            "attr_name_list_comp": db.render_list_comprehension(
                items="node_map.attributes", item_name="node_properties.name"
            ),
            "attr_props_list_comp": db.render_list_comprehension(
                items="node_attribute.properties", item_name="node_properties.property_type"
            ),
            "rel_name_list_comp": db.render_list_comprehension(
                items="node_map.relationships", item_name="node_properties.name"
            ),
            "rel_peers_list_comp": db.render_list_comprehension(
                items="node_relationship.relationships", item_name="node_properties.peer_id"
            ),
            "element_props_list_comp": db.render_list_comprehension(
                items="node_single_relationship.properties", item_name="node_properties.property_type"
            ),
        }
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
                "db_labels": json.dumps(list(enriched_node.identifier.labels)),
                "label": enriched_node.label,
                "changed_at": enriched_node.changed_at.to_string() if enriched_node.changed_at else None,
                "action": enriched_node.action.value,
                "path_identifier": enriched_node.path_identifier,
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

    def __init__(self, diff_root_uuid: str, diff_nodes: Iterable[EnrichedDiffNode], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.diff_root_uuid = diff_root_uuid
        self.diff_nodes = diff_nodes

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        parent_node_map: dict[str, dict[str, str]] = {}
        for diff_node in self.diff_nodes:
            if diff_node.uuid not in parent_node_map:
                parent_node_map[diff_node.uuid] = {}
            for relationship in diff_node.relationships:
                for parent_node in relationship.nodes:
                    parent_node_map[diff_node.uuid][relationship.name] = parent_node.uuid
        self.params = {"root_uuid": self.diff_root_uuid, "parent_node_map": parent_node_map}
        query = """
WITH keys($parent_node_map) AS child_node_uuids
MATCH (diff_root:DiffRoot {uuid: $root_uuid})
MATCH (diff_root)-[:DIFF_HAS_NODE]->(child_node:DiffNode)
WHERE child_node.uuid IN child_node_uuids
CALL {
    WITH diff_root, child_node
    WITH diff_root, child_node, $parent_node_map[child_node.uuid] AS sub_map
    WITH diff_root, child_node, sub_map, keys(sub_map) AS relationship_names
    MATCH (child_node)-[:DIFF_HAS_RELATIONSHIP]->(diff_rel_group:DiffRelationship)
    WHERE diff_rel_group.name IN relationship_names
    WITH diff_root, diff_rel_group, toString(sub_map[diff_rel_group.name]) AS parent_uuid
    MATCH (diff_root)-[:DIFF_HAS_NODE]->(parent_node:DiffNode {uuid: parent_uuid})
    MERGE (diff_rel_group)-[:DIFF_HAS_NODE]->(parent_node)
}
        """
        self.add_to_query(query)
