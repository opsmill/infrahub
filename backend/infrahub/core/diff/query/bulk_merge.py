from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


class BulkMergeNodeExistenceQuery(Query):
    """Bulk merge IS_PART_OF and HAS_ATTRIBUTE edges from source branch to target branch.

    Any edge on the source branch represents a change that needs merging.
    A branch can only be merged once, so no time filtering is needed beyond
    branch identity and current active-ness (to IS NULL).

    Nodes that were both created and deleted on the source branch are skipped
    (both an active and deleted IS_PART_OF exist on the source branch).
    """

    name = "bulk_merge_node_existence"
    type = QueryType.WRITE
    insert_return = False
    raise_error_if_empty = False

    def __init__(
        self,
        at: Timestamp,
        target_branch: Branch,
        excluded_uuids: list[str],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.at = at
        self.target_branch = target_branch
        self.source_branch_name = self.branch.name
        self.excluded_uuids = excluded_uuids

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "at": self.at.to_string(),
            "branch_level": self.target_branch.hierarchy_level,
            "target_branch": self.target_branch.name,
            "source_branch": self.source_branch_name,
            "global_branch": GLOBAL_BRANCH_NAME,
            "excluded_uuids": self.excluded_uuids,
        }
        query = """
// ==============================
// Phase 1: Merge IS_PART_OF edges (node existence)
// ==============================
MATCH (n:Node)-[src:IS_PART_OF]->(root:Root)
WHERE src.branch = $source_branch
AND src.to IS NULL
AND NOT n.uuid IN $excluded_uuids
AND n.branch_support = "aware"
// ------------------------------
// Skip nodes created and then deleted on the same branch (both edges exist)
// ------------------------------
AND NOT (
    src.status = "deleted"
    AND EXISTS {
        MATCH (n)-[:IS_PART_OF {branch: $source_branch, status: "active"}]->(root)
    }
)
AND NOT (
    src.status = "active"
    AND EXISTS {
        MATCH (n)-[:IS_PART_OF {branch: $source_branch, status: "deleted"}]->(root)
    }
)
WITH n, root, src
// -------------------------
// close active IS_PART_OF on target branch when deleting
// -------------------------
CALL (n, root, src) {
    OPTIONAL MATCH (n)-[tgt:IS_PART_OF {branch: $target_branch, status: "active"}]->(root)
    WHERE src.status = "deleted"
    AND tgt.to IS NULL
    SET tgt.to = $at, tgt.to_user_id = src.from_user_id
}
// -------------------------
// create new IS_PART_OF on target branch if not exists
// -------------------------
CALL (n, root, src) {
    OPTIONAL MATCH (n)-[existing:IS_PART_OF {branch: $target_branch, status: src.status}]->(root)
    WHERE existing.to IS NULL
    WITH n, root, src
    WHERE existing IS NULL
    CREATE (n)-[new_edge:IS_PART_OF]->(root)
    SET new_edge = properties(src)
    SET new_edge.branch = $target_branch, new_edge.branch_level = $branch_level, new_edge.from = $at, new_edge.to = NULL, new_edge.to_user_id = NULL
    WITH n, src
    WHERE src.status = "active"
    // ------------------------------
    // Only set created_at if not already set. For migrated nodes, use the earliest
    // created_at across all vertices with the same UUID.
    // ------------------------------
    CALL (n, src) {
        WITH n, src
        WHERE n.created_at IS NULL
        OPTIONAL MATCH (earliest:Node {uuid: n.uuid})
        WHERE earliest.created_at IS NOT NULL
        WITH n, src, earliest
        ORDER BY earliest.created_at ASC
        LIMIT 1
        SET n.created_at = COALESCE(earliest.created_at, $at),
            n.created_by = COALESCE(earliest.created_by, src.from_user_id)
    }
}
// -------------------------
// cascade close all attribute and relationship edges when node is deleted
// -------------------------
CALL (n, src) {
    WITH n, src
    WHERE src.status = "deleted"
    // ------------------------------
    // Only cascade if the UUID is truly deleted (no other vertex with an active IS_PART_OF
    // on the source branch). For migrated nodes, the old vertex is "deleted" but the new
    // vertex, with the same UUID, is "active"
    // ------------------------------
    AND NOT EXISTS {
        MATCH (other:Node {uuid: n.uuid})-[active_ipo:IS_PART_OF {branch: $source_branch, status: "active"}]->(:Root)
        WHERE active_ipo.to IS NULL
        AND other <> n
    }
    // ------------------------------
    // close IS_RELATED and HAS_ATTRIBUTE sub-edges
    // ------------------------------
    OPTIONAL MATCH (n)-[rel1:IS_RELATED|HAS_ATTRIBUTE]-(field:Relationship|Attribute)-[rel2]-(p)
    WHERE (p.uuid IS NULL OR n.uuid <> p.uuid)
    AND rel1.branch = $target_branch AND rel2.branch = $target_branch
    AND rel1.status = "active" AND rel2.status = "active"
    AND rel1.to IS NULL AND rel2.to IS NULL
    SET rel1.to = $at, rel1.to_user_id = src.from_user_id
    SET rel2.to = $at, rel2.to_user_id = src.from_user_id
    // ------------------------------
    // close HAS_OWNER and HAS_SOURCE edges pointing to this deleted node
    // ------------------------------
    WITH DISTINCT n, src
    OPTIONAL MATCH (n)<-[owner_source_rel:HAS_OWNER|HAS_SOURCE]-()
    WHERE owner_source_rel.branch = $target_branch
    AND owner_source_rel.status = "active"
    AND owner_source_rel.to IS NULL
    SET owner_source_rel.to = $at, owner_source_rel.to_user_id = src.from_user_id
}

// ==============================
// Phase 2: Merge HAS_ATTRIBUTE edges (attribute existence)
// ==============================
WITH 1 AS phase_separator LIMIT 1
MATCH (n:Node)-[src:HAS_ATTRIBUTE]->(a:Attribute)
WHERE src.branch = $source_branch
AND src.to IS NULL
AND NOT n.uuid IN $excluded_uuids
AND n.branch_support = "aware"
// ------------------------------
// Skip attributes created and deleted on the same branch
// ------------------------------
AND NOT (
    src.status = "deleted"
    AND EXISTS {
        MATCH (n)-[:HAS_ATTRIBUTE {branch: $source_branch, status: "active"}]->(a)
    }
)
AND NOT (
    src.status = "active"
    AND EXISTS {
        MATCH (n)-[del_src:HAS_ATTRIBUTE {branch: $source_branch, status: "deleted"}]->(a)
        WHERE del_src.to IS NULL
    }
)
WITH n, a, src
// -------------------------
// close active HAS_ATTRIBUTE on target branch when deleting
// -------------------------
CALL (n, a, src) {
    OPTIONAL MATCH (n)-[tgt:HAS_ATTRIBUTE {branch: $target_branch, status: "active"}]->(a)
    WHERE src.status = "deleted"
    AND tgt.to IS NULL
    SET tgt.to = $at, tgt.to_user_id = src.from_user_id
}
// -------------------------
// create new HAS_ATTRIBUTE on target branch if not exists
// -------------------------
CALL (n, a, src) {
    OPTIONAL MATCH (n)-[existing:HAS_ATTRIBUTE {branch: $target_branch, status: src.status}]->(a)
    WHERE existing.to IS NULL OR existing.to >= $at
    WITH n, a, src
    WHERE existing IS NULL
    CREATE (n)-[new_edge:HAS_ATTRIBUTE]->(a)
    SET new_edge = properties(src)
    SET new_edge.branch = $target_branch, new_edge.branch_level = $branch_level, new_edge.from = $at, new_edge.to = NULL, new_edge.to_user_id = NULL
    WITH a, src
    WHERE src.status = "active"
    AND a.created_at IS NULL
    SET a.created_at = $at, a.created_by = src.from_user_id
}
        """
        self.add_to_query(query=query)


class BulkMergePropertyEdgesQuery(Query):
    """Bulk merge HAS_VALUE, IS_PROTECTED, HAS_OWNER, HAS_SOURCE edges.

    These are singleton property edges: at most one active per parent per branch.
    When merging, close the old target edge (to different child) and create the new one.
    """

    name = "bulk_merge_property_edges"
    type = QueryType.WRITE
    insert_return = False
    raise_error_if_empty = False

    def __init__(
        self,
        at: Timestamp,
        target_branch: Branch,
        excluded_uuids: list[str],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.at = at
        self.target_branch = target_branch
        self.source_branch_name = self.branch.name
        self.excluded_uuids = excluded_uuids

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "at": self.at.to_string(),
            "branch_level": self.target_branch.hierarchy_level,
            "target_branch": self.target_branch.name,
            "source_branch": self.source_branch_name,
            "global_branch": GLOBAL_BRANCH_NAME,
            "excluded_uuids": self.excluded_uuids,
        }
        query = """
// ==============================
// TODO: ensure we don't add status=active edges to deleted attributes or relationships
// should add tests for this as well
// ==============================

// ==============================
// Merge property edges: Attribute properties + Relationship properties
// ==============================
CALL () {
    // ------------------------------
    // Attribute properties: (Node)-[:HAS_ATTRIBUTE]->(Attribute)-[src]->(child)
    // ------------------------------
    MATCH (n:Node)-[:HAS_ATTRIBUTE]-(field:Attribute)-[src:HAS_VALUE|IS_PROTECTED|HAS_OWNER|HAS_SOURCE]->(child)
    WHERE src.branch = $source_branch
    AND src.to IS NULL
    AND NOT n.uuid IN $excluded_uuids
    AND field.branch_support = "aware"
    RETURN DISTINCT field, child, src

    UNION

    // ------------------------------
    // Relationship properties: (Node)-[:IS_RELATED]-(Relationship)-[src]->(child)
    // Both nodes in the relationship must be alive on target and not excluded
    // ------------------------------
    MATCH (n:Node)-[:IS_RELATED]-(field:Relationship)-[src:HAS_VALUE|IS_PROTECTED|HAS_OWNER|HAS_SOURCE]->(child)
    WHERE src.branch = $source_branch
    AND src.to IS NULL
    AND NOT n.uuid IN $excluded_uuids
    AND field.branch_support = "aware"
    // The peer on the other side must be alive and not excluded
    AND EXISTS {
        MATCH (peer:Node)-[:IS_RELATED]-(field)
        WHERE peer <> n
        AND NOT peer.uuid IN $excluded_uuids
        AND EXISTS {
            MATCH (peer)-[p_ipo:IS_PART_OF]->(:Root)
            WHERE p_ipo.branch IN [$target_branch, $global_branch]
            AND p_ipo.status = "active"
            AND (p_ipo.to IS NULL OR p_ipo.to >= $at)
        }
    }
    RETURN DISTINCT field, child, src
}
WITH field, child, src, type(src) AS edge_type, src.status AS prop_status, src.from_user_id AS prop_from_user_id
// -------------------------
// close any active target edge of same type from same field pointing to different child
// -------------------------
CALL (field, child, edge_type, prop_from_user_id) {
    OPTIONAL MATCH (field)-[tgt:$(edge_type)]->(other_child)
    WHERE tgt.branch = $target_branch
    AND tgt.status = "active"
    AND tgt.to IS NULL
    AND other_child <> child
    SET tgt.to = $at, tgt.to_user_id = prop_from_user_id
}
// -------------------------
// check for existing edge on target branch
// -------------------------
CALL (field, child, edge_type, prop_status) {
    OPTIONAL MATCH (field)-[existing]->(child)
    WHERE type(existing) = edge_type
    AND existing.branch = $target_branch
    AND existing.status = prop_status
    AND existing.to IS NULL
    RETURN existing
}
WITH field, src, child, edge_type, prop_status, prop_from_user_id
WHERE existing IS NULL
// -------------------------
// create new edge per type
// -------------------------
CALL (field, src, child, edge_type, prop_status, prop_from_user_id) {
    CREATE (field)-[new_e:$(edge_type)]->(child)
    SET new_e = properties(src)
    SET new_e.branch = $target_branch,
        new_e.branch_level = $branch_level,
        new_e.from = $at,
        new_e.to = NULL,
        new_e.to_user_id = NULL
}
        """
        self.add_to_query(query=query)


class BulkMergeRelationshipEdgesQuery(Query):
    """Bulk merge IS_RELATED edges from source branch to target branch.

    Handles direction preservation and hierarchy properties.
    """

    name = "bulk_merge_relationship_edges"
    type = QueryType.WRITE
    insert_return = False
    raise_error_if_empty = False

    def __init__(
        self,
        at: Timestamp,
        target_branch: Branch,
        excluded_uuids: list[str],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.at = at
        self.target_branch = target_branch
        self.source_branch_name = self.branch.name
        self.excluded_uuids = excluded_uuids

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "at": self.at.to_string(),
            "branch_level": self.target_branch.hierarchy_level,
            "target_branch": self.target_branch.name,
            "source_branch": self.source_branch_name,
            "global_branch": GLOBAL_BRANCH_NAME,
            "excluded_uuids": self.excluded_uuids,
        }
        query = """
// ==============================
// Find IS_RELATED edge pairs on the source branch
// ==============================
MATCH (n:Node)-[src1:IS_RELATED {branch: $source_branch}]-(rel:Relationship)-[src2:IS_RELATED {branch: $source_branch}]-(peer:Node)
WHERE src1.to IS NULL AND src2.to IS NULL
AND NOT n.uuid IN $excluded_uuids
AND NOT peer.uuid IN $excluded_uuids
AND rel.branch_support = "aware"
AND n.uuid <> peer.uuid
// -------------------------
// Deduplicate: the undirected match finds each pair twice (n<->peer and peer<->n)
// -------------------------
AND elementId(n) < elementId(peer)
// -------------------------
// determine directions and hierarchy from source edges
// -------------------------
WITH n, rel, peer, src1, src2,
    CASE WHEN startNode(src1) = n THEN "r" ELSE "l" END AS r1_dir,
    CASE WHEN startNode(src2) = rel THEN "r" ELSE "l" END AS r2_dir,
    src1.hierarchy AS r1_hierarchy,
    src2.hierarchy AS r2_hierarchy,
    src1.from_user_id AS r1_from_user_id,
    src2.from_user_id AS r2_from_user_id,
    src1.status AS related_rel_status
// -------------------------
// close active IS_RELATED pair on target branch when deleting
// -------------------------
CALL (n, rel, peer, related_rel_status, r1_from_user_id, r2_from_user_id) {
    OPTIONAL MATCH (n)
        -[tgt1:IS_RELATED {branch: $target_branch, status: "active"}]
        -(rel)
        -[tgt2:IS_RELATED {branch: $target_branch, status: "active"}]
        -(peer)
    WHERE related_rel_status = "deleted"
    AND tgt1.to IS NULL AND tgt2.to IS NULL
    SET tgt1.to = $at, tgt1.to_user_id = r1_from_user_id
    SET tgt2.to = $at, tgt2.to_user_id = r2_from_user_id
}
// -------------------------
// For active rows, both n and peer must be alive on the target branch.
// Deleted rows can be created regardless (they record the historical relationship).
// Filtering at the row level prevents orphan rel1/rel2 (one side without the other).
// -------------------------
WITH *
WHERE related_rel_status = "deleted"
   OR (
       EXISTS {
           MATCH (n)-[ipo:IS_PART_OF]->(:Root)
           WHERE ipo.branch IN [$target_branch, $global_branch]
           AND ipo.status = "active"
           AND ipo.to IS NULL
       }
       AND EXISTS {
           MATCH (peer)-[ipo:IS_PART_OF]->(:Root)
           WHERE ipo.branch IN [$target_branch, $global_branch]
           AND ipo.status = "active"
           AND ipo.to IS NULL
       }
   )
// -------------------------
// create IS_RELATED edges with correct direction (only if not already existing)
// -------------------------
CALL (n, rel, r1_dir, r1_hierarchy, related_rel_status, r1_from_user_id) {
    WITH *
    WHERE r1_dir = "r"
    AND NOT EXISTS {
        MATCH (n)-[:IS_RELATED {branch: $target_branch, status: related_rel_status}]->(rel)
    }
    CREATE (n)-[:IS_RELATED {
        branch: $target_branch, branch_level: $branch_level, from: $at,
        status: related_rel_status, hierarchy: r1_hierarchy, from_user_id: r1_from_user_id
    }]->(rel)
}
CALL (n, rel, r1_dir, r1_hierarchy, related_rel_status, r1_from_user_id) {
    WITH *
    WHERE r1_dir = "l"
    AND NOT EXISTS {
        MATCH (n)<-[:IS_RELATED {branch: $target_branch, status: related_rel_status}]-(rel)
    }
    CREATE (n)<-[:IS_RELATED {
        branch: $target_branch, branch_level: $branch_level, from: $at,
        status: related_rel_status, hierarchy: r1_hierarchy, from_user_id: r1_from_user_id
    }]-(rel)
}
CALL (rel, peer, r2_dir, r2_hierarchy, related_rel_status, r2_from_user_id) {
    WITH *
    WHERE r2_dir = "r"
    AND NOT EXISTS {
        MATCH (rel)-[:IS_RELATED {branch: $target_branch, status: related_rel_status}]->(peer)
    }
    CREATE (rel)-[:IS_RELATED {
        branch: $target_branch, branch_level: $branch_level, from: $at,
        status: related_rel_status, hierarchy: r2_hierarchy, from_user_id: r2_from_user_id
    }]->(peer)
}
CALL (rel, peer, r2_dir, r2_hierarchy, related_rel_status, r2_from_user_id) {
    WITH *
    WHERE r2_dir = "l"
    AND NOT EXISTS {
        MATCH (rel)<-[:IS_RELATED {branch: $target_branch, status: related_rel_status}]-(peer)
    }
    CREATE (rel)<-[:IS_RELATED {
        branch: $target_branch, branch_level: $branch_level, from: $at,
        status: related_rel_status, hierarchy: r2_hierarchy, from_user_id: r2_from_user_id
    }]-(peer)
}
// -------------------------
// set Relationship vertex metadata when adding
// -------------------------
WITH rel, r1_from_user_id
WHERE rel.created_at IS NULL
SET rel.created_at = $at, rel.created_by = r1_from_user_id
        """
        self.add_to_query(query=query)
