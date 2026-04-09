from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


class CypherMergeExclusionQuery(Query):
    """Query the diff graph for node UUIDs that should be excluded from the bulk merge.

    Only conflicted nodes are excluded. Migrated-kind nodes are handled by the bulk
    queries directly — migrations create explicit source-branch edges for both old and
    new Node vertices, and the `to IS NULL` filter naturally selects the correct state.
    """

    name = "cypher_merge_exclusion"
    type = QueryType.READ

    def __init__(
        self,
        diff_branch_name: str,
        tracking_id: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.diff_branch_name = diff_branch_name
        self.tracking_id = tracking_id

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "diff_branch_name": self.diff_branch_name,
            "tracking_id": self.tracking_id,
        }
        query = """
MATCH (root:DiffRoot)
WHERE (root.is_merged IS NULL OR root.is_merged <> TRUE)
AND root.tracking_id = $tracking_id
AND root.diff_branch = $diff_branch_name
MATCH (root)-[:DIFF_HAS_NODE]->(dn:DiffNode)
WHERE EXISTS {
    MATCH (dn)-[:DIFF_HAS_CONFLICT]->(c:DiffConflict)
    WHERE c.selected_branch IS NOT NULL
} OR EXISTS {
    MATCH (dn)-[:DIFF_HAS_ATTRIBUTE]->(:DiffAttribute)
        -[:DIFF_HAS_PROPERTY]->(:DiffProperty)-[:DIFF_HAS_CONFLICT]->(c:DiffConflict)
    WHERE c.selected_branch IS NOT NULL
} OR EXISTS {
    MATCH (dn)-[:DIFF_HAS_RELATIONSHIP]->(:DiffRelationship)
        -[:DIFF_HAS_ELEMENT]->(:DiffRelationshipElement)-[:DIFF_HAS_CONFLICT]->(c:DiffConflict)
    WHERE c.selected_branch IS NOT NULL
} OR EXISTS {
    MATCH (dn)-[:DIFF_HAS_RELATIONSHIP]->(:DiffRelationship)
        -[:DIFF_HAS_ELEMENT]->(:DiffRelationshipElement)-[:DIFF_HAS_PROPERTY]->(:DiffProperty)
        -[:DIFF_HAS_CONFLICT]->(c:DiffConflict)
    WHERE c.selected_branch IS NOT NULL
}
WITH DISTINCT dn.uuid AS uuid
        """
        self.return_labels = ["uuid"]
        self.add_to_query(query=query)

    def get_conflict_uuids(self) -> set[str]:
        return {result.get_as_type("uuid", str) for result in self.get_results()}


class CypherMergeNodeExistenceQuery(Query):
    """Bulk merge IS_PART_OF and HAS_ATTRIBUTE edges from source branch to target branch.

    Any edge on the source branch represents a change that needs merging.
    A branch can only be merged once, so no time filtering is needed beyond
    branch identity and current activity (to IS NULL).

    Nodes that were both created and deleted on the source branch are skipped
    (both an active and deleted IS_PART_OF exist on the source branch).
    """

    name = "cypher_merge_node_existence"
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
AND n.branch_support <> "local"
// Skip nodes created and then deleted on the same branch (both edges exist)
AND NOT (
    src.status = "deleted"
    AND EXISTS {
        MATCH (n)-[:IS_PART_OF {branch: $source_branch, status: "active"}]->(root)
    }
)
AND NOT (
    src.status = "active"
    AND EXISTS {
        MATCH (n)-[del_src:IS_PART_OF {branch: $source_branch, status: "deleted"}]->(root)
        WHERE del_src.to IS NULL
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
    WHERE existing.to IS NULL OR existing.to >= $at
    WITH n, root, src, existing
    WHERE existing IS NULL
    CREATE (n)-[new_edge:IS_PART_OF]->(root)
    SET new_edge = properties(src)
    SET new_edge.branch = $target_branch, new_edge.branch_level = $branch_level, new_edge.from = $at
    WITH n, src
    WHERE src.status = "active"
    // Only set created_at if not already set. For migrated nodes, use the earliest
    // created_at across all vertices with the same UUID.
    CALL (n, src) {
        WITH n, src WHERE n.created_at IS NULL
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
    // Only cascade if the UUID is truly deleted (no other vertex with an active IS_PART_OF
    // on the source branch). For migrated nodes, the old vertex is "deleted" but the new
    // vertex, with the same UUID, is "active"
    AND NOT EXISTS {
        MATCH (other:Node {uuid: n.uuid})-[active_ipo:IS_PART_OF {branch: $source_branch, status: "active"}]->(:Root)
        WHERE active_ipo.to IS NULL
        AND other <> n
    }
    // close IS_RELATED and HAS_ATTRIBUTE sub-edges
    CALL (n) {
        OPTIONAL MATCH (n)-[rel1:IS_RELATED]-(field:Relationship)-[rel2]-(p)
        WHERE (p.uuid IS NULL OR n.uuid <> p.uuid)
        AND rel1.branch = $target_branch AND rel2.branch = $target_branch
        AND rel1.status = "active" AND rel2.status = "active"
        RETURN rel1, rel2
        UNION
        OPTIONAL MATCH (n)-[rel1:HAS_ATTRIBUTE]->(field:Attribute)-[rel2]->()
        WHERE type(rel2) <> "HAS_ATTRIBUTE"
        AND rel1.branch = $target_branch AND rel2.branch = $target_branch
        AND rel1.status = "active" AND rel2.status = "active"
        RETURN rel1, rel2
    }
    WITH n, src, rel1, rel2
    WHERE rel1.to IS NULL AND rel2.to IS NULL
    SET rel1.to = $at, rel1.to_user_id = src.from_user_id
    SET rel2.to = $at, rel2.to_user_id = src.from_user_id
    // close HAS_OWNER and HAS_SOURCE edges pointing to this deleted node
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
AND n.branch_support <> "local"
// Skip attributes created and deleted on the same branch
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
    WITH n, a, src, existing
    WHERE existing IS NULL
    CREATE (n)-[new_edge:HAS_ATTRIBUTE]->(a)
    SET new_edge = properties(src)
    SET new_edge.branch = $target_branch, new_edge.branch_level = $branch_level, new_edge.from = $at
    WITH a, src
    WHERE src.status = "active"
    AND a.created_at IS NULL
    SET a.created_at = $at, a.created_by = src.from_user_id
}
        """
        self.add_to_query(query=query)


class CypherMergePropertyEdgesQuery(Query):
    """Bulk merge HAS_VALUE, IS_PROTECTED, HAS_OWNER, HAS_SOURCE edges.

    These are singleton property edges: at most one active per parent per branch.
    When merging, close the old target edge (to different child) and create the new one.
    """

    name = "cypher_merge_property_edges"
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
// Merge property edges: Attribute properties + Relationship properties
// ==============================
CALL () {
    // --- Attribute properties: (Node)-[:HAS_ATTRIBUTE]->(Attribute)-[src]->(child) ---
    MATCH (n:Node)-[:HAS_ATTRIBUTE]-(field:Attribute)-[src:HAS_VALUE|IS_PROTECTED|HAS_OWNER|HAS_SOURCE]->(child)
    WHERE src.branch = $source_branch
    AND src.to IS NULL
    AND NOT n.uuid IN $excluded_uuids
    AND n.branch_support <> "local"
    // Node must be alive on target branch
    AND EXISTS {
        MATCH (n)-[n_ipo:IS_PART_OF]->(:Root)
        WHERE n_ipo.branch IN [$target_branch, $global_branch]
        AND n_ipo.status = "active"
        AND (n_ipo.to IS NULL OR n_ipo.to >= $at)
    }
    RETURN DISTINCT elementId(src) AS _src_id, field, child, src, type(src) AS edge_type

    UNION

    // --- Relationship properties: (Node)-[:IS_RELATED]-(Relationship)-[src]->(child) ---
    // Both nodes in the relationship must be alive on target and not excluded
    MATCH (n:Node)-[:IS_RELATED]-(field:Relationship)-[src:HAS_VALUE|IS_PROTECTED|HAS_OWNER|HAS_SOURCE]->(child)
    WHERE src.branch = $source_branch
    AND src.to IS NULL
    AND NOT n.uuid IN $excluded_uuids
    AND n.branch_support <> "local"
    AND EXISTS {
        MATCH (n)-[n_ipo:IS_PART_OF]->(:Root)
        WHERE n_ipo.branch IN [$target_branch, $global_branch]
        AND n_ipo.status = "active"
        AND (n_ipo.to IS NULL OR n_ipo.to >= $at)
    }
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
    RETURN DISTINCT elementId(src) AS _src_id, field, child, src, type(src) AS edge_type
}
WITH DISTINCT _src_id, field, child, src, edge_type
WITH field, child, src, edge_type, src.status AS prop_status, src.from_user_id AS prop_from_user_id
// -------------------------
// close any active target edge of same type from same field pointing to different child
// -------------------------
CALL (field, child, edge_type, prop_from_user_id) {
    MATCH (field)-[tgt]->(other_child)
    WHERE type(tgt) = edge_type
    AND tgt.branch = $target_branch
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
    AND (existing.to IS NULL OR existing.to >= $at)
    RETURN existing
}
WITH field, child, edge_type, prop_status, prop_from_user_id, existing
WHERE existing IS NULL
// -------------------------
// create new edge per type (edge type cannot be parameterized in CREATE)
// -------------------------
CALL (field, child, edge_type, prop_status, prop_from_user_id) {
    WITH field, child, prop_status, prop_from_user_id
    WHERE edge_type = "HAS_VALUE"
    CREATE (field)-[:HAS_VALUE {
        branch: $target_branch, branch_level: $branch_level, from: $at,
        status: prop_status, from_user_id: prop_from_user_id
    }]->(child)
}
CALL (field, child, edge_type, prop_status, prop_from_user_id) {
    WITH field, child, prop_status, prop_from_user_id
    WHERE edge_type = "IS_PROTECTED"
    CREATE (field)-[:IS_PROTECTED {
        branch: $target_branch, branch_level: $branch_level, from: $at,
        status: prop_status, from_user_id: prop_from_user_id
    }]->(child)
}
CALL (field, child, edge_type, prop_status, prop_from_user_id) {
    WITH field, child, prop_status, prop_from_user_id
    WHERE edge_type = "HAS_OWNER"
    CREATE (field)-[:HAS_OWNER {
        branch: $target_branch, branch_level: $branch_level, from: $at,
        status: prop_status, from_user_id: prop_from_user_id
    }]->(child)
}
CALL (field, child, edge_type, prop_status, prop_from_user_id) {
    WITH field, child, prop_status, prop_from_user_id
    WHERE edge_type = "HAS_SOURCE"
    CREATE (field)-[:HAS_SOURCE {
        branch: $target_branch, branch_level: $branch_level, from: $at,
        status: prop_status, from_user_id: prop_from_user_id
    }]->(child)
}
        """
        self.add_to_query(query=query)


class CypherMergeRelationshipEdgesQuery(Query):
    """Bulk merge IS_RELATED edges from source branch to target branch.

    Handles direction preservation and hierarchy properties.
    """

    name = "cypher_merge_relationship_edges"
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
AND n.branch_support <> "local"
AND peer.branch_support <> "local"
AND n.uuid <> peer.uuid
// Deduplicate: the undirected match finds each pair twice (n<->peer and peer<->n)
AND elementId(n) < elementId(peer)
// Both nodes must be alive on the target branch
AND EXISTS {
    MATCH (n)-[n_ipo:IS_PART_OF]->(:Root)
    WHERE n_ipo.branch IN [$target_branch, $global_branch]
    AND n_ipo.status = "active"
    AND (n_ipo.to IS NULL OR n_ipo.to >= $at)
}
AND EXISTS {
    MATCH (peer)-[p_ipo:IS_PART_OF]->(:Root)
    WHERE p_ipo.branch IN [$target_branch, $global_branch]
    AND p_ipo.status = "active"
    AND (p_ipo.to IS NULL OR p_ipo.to >= $at)
}
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
// check for existing IS_RELATED pair on target branch
// -------------------------
CALL (n, rel, peer, related_rel_status) {
    OPTIONAL MATCH (n)
        -[existing1:IS_RELATED {branch: $target_branch, status: related_rel_status}]
        -(rel)
        -[existing2:IS_RELATED {branch: $target_branch, status: related_rel_status}]
        -(peer)
    WHERE (existing1.to IS NULL OR existing1.to >= $at)
    AND (existing2.to IS NULL OR existing2.to >= $at)
    RETURN existing1, existing2
}
WITH n, rel, peer, r1_dir, r2_dir, r1_hierarchy, r2_hierarchy,
    r1_from_user_id, r2_from_user_id, related_rel_status, existing1, existing2
WHERE existing1 IS NULL AND existing2 IS NULL
// -------------------------
// create IS_RELATED edges with correct direction
// -------------------------
CALL (n, rel, r1_dir, r1_hierarchy, related_rel_status, r1_from_user_id) {
    WITH n, rel, r1_dir, r1_hierarchy, related_rel_status, r1_from_user_id
    WHERE r1_dir = "r"
    CREATE (n)-[:IS_RELATED {
        branch: $target_branch, branch_level: $branch_level, from: $at,
        status: related_rel_status, hierarchy: r1_hierarchy, from_user_id: r1_from_user_id
    }]->(rel)
}
CALL (n, rel, r1_dir, r1_hierarchy, related_rel_status, r1_from_user_id) {
    WITH n, rel, r1_dir, r1_hierarchy, related_rel_status, r1_from_user_id
    WHERE r1_dir = "l"
    CREATE (n)<-[:IS_RELATED {
        branch: $target_branch, branch_level: $branch_level, from: $at,
        status: related_rel_status, hierarchy: r1_hierarchy, from_user_id: r1_from_user_id
    }]-(rel)
}
CALL (rel, peer, r2_dir, r2_hierarchy, related_rel_status, r2_from_user_id) {
    WITH rel, peer, r2_dir, r2_hierarchy, related_rel_status, r2_from_user_id
    WHERE r2_dir = "r"
    CREATE (rel)-[:IS_RELATED {
        branch: $target_branch, branch_level: $branch_level, from: $at,
        status: related_rel_status, hierarchy: r2_hierarchy, from_user_id: r2_from_user_id
    }]->(peer)
}
CALL (rel, peer, r2_dir, r2_hierarchy, related_rel_status, r2_from_user_id) {
    WITH rel, peer, r2_dir, r2_hierarchy, related_rel_status, r2_from_user_id
    WHERE r2_dir = "l"
    CREATE (rel)<-[:IS_RELATED {
        branch: $target_branch, branch_level: $branch_level, from: $at,
        status: related_rel_status, hierarchy: r2_hierarchy, from_user_id: r2_from_user_id
    }]-(peer)
}
// set Relationship vertex metadata when adding
WITH rel, r1_from_user_id
WHERE rel.created_at IS NULL
SET rel.created_at = $at, rel.created_by = r1_from_user_id
        """
        self.add_to_query(query=query)


class CypherMergeAffectedNodeUUIDsQuery(Query):
    """Get all node UUIDs from the diff graph for metadata updates.

    The DiffMergeMetadataQuery itself filters to only update nodes that have actual
    edge changes at $at on the target branch, so passing all diff node UUIDs is safe.
    """

    name = "cypher_merge_affected_node_uuids"
    type = QueryType.READ

    def __init__(
        self,
        at: Timestamp,
        target_branch: Branch,
        tracking_id: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.at = at
        self.target_branch = target_branch
        self.tracking_id = tracking_id

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "at": self.at.to_string(),
            "target_branch": self.target_branch.name,
            "source_branch": self.branch.name,
            "tracking_id": self.tracking_id,
        }
        query = """
MATCH (root:DiffRoot)-[:DIFF_HAS_NODE]->(dn:DiffNode)
WHERE root.diff_branch = $source_branch
AND root.tracking_id = $tracking_id
AND (root.is_merged IS NULL OR root.is_merged <> TRUE)
WITH DISTINCT dn.uuid AS uuid
        """
        self.return_labels = ["uuid"]
        self.add_to_query(query=query)

    def get_node_uuids(self) -> list[str]:
        return [result.get_as_type("uuid", str) for result in self.get_results()]
