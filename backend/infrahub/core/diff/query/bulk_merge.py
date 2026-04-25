from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


# TODO: is changing an edge multiple times captured correctly?
# eg car.num = 1, car.num = 2, car.num = 1 before merge
# should the merge queries start with the latest edge on the source branch between any two vertices and use that as a guide
# instead of using every edge on the source branch?


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
// ------------------------------
// Resolve the currently-active target-branch Node vertex for this UUID.
// After a post-fork target-branch node-kind migration, a branch-side write
// anchored on the pre-migration vertex (``n``) must act on the post-migration
// sibling that holds the target-branch active IS_PART_OF. If no such vertex
// exists (e.g. the UUID is new on the source branch), ``tgt_n = n``. Only
// close / cascade operations use ``tgt_n``; creates stay anchored on ``n``
// so a source-branch node-kind migration still lands its new-kind vertex on
// target.
// ------------------------------
CALL (n) {
    OPTIONAL MATCH (tgt_candidate:Node {uuid: n.uuid})-[tgt_ipo:IS_PART_OF {branch: $target_branch, status: "active"}]->(:Root)
    WHERE tgt_ipo.to IS NULL
    WITH tgt_candidate, tgt_ipo
    ORDER BY tgt_ipo.from DESC
    LIMIT 1
    RETURN tgt_candidate
}
WITH n, COALESCE(tgt_candidate, n) AS tgt_n, root, src
// -------------------------
// close active IS_PART_OF on target branch when deleting (operates on ``tgt_n``
// so a branch-side delete on the pre-migration sibling closes the current
// target-active post-migration sibling)
// -------------------------
CALL (tgt_n, root, src) {
    OPTIONAL MATCH (tgt_n)-[tgt:IS_PART_OF {branch: $target_branch, status: "active"}]->(root)
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
// (operates on ``tgt_n`` so the post-migration sibling's active sub-edges
// are closed)
// -------------------------
CALL (n, tgt_n, src) {
    WITH n, tgt_n, src
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
    OPTIONAL MATCH (tgt_n)-[rel1:IS_RELATED|HAS_ATTRIBUTE]-(field:Relationship|Attribute)-[rel2]-(p)
    WHERE (p.uuid IS NULL OR tgt_n.uuid <> p.uuid)
    AND rel1.branch = $target_branch AND rel2.branch = $target_branch
    AND rel1.status = "active" AND rel2.status = "active"
    AND rel1.to IS NULL AND rel2.to IS NULL
    SET rel1.to = $at, rel1.to_user_id = src.from_user_id
    SET rel2.to = $at, rel2.to_user_id = src.from_user_id
    // ------------------------------
    // close HAS_OWNER and HAS_SOURCE edges pointing to this deleted node
    // ------------------------------
    WITH DISTINCT tgt_n, src
    OPTIONAL MATCH (tgt_n)<-[owner_source_rel:HAS_OWNER|HAS_SOURCE]-()
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
    }
)
WITH n, a, src
// -------------------------
// four possible cases to handle
// 1. source active + latest target active -> do nothing
// 2. source active + latest target NULL/deleted -> create HAS_ATTRIBUTE
// 3. source deleted + latest target active -> close latest target HAS_ATTRIBUTE
// 4. source deleted + latest target NULL/deleted -> do nothing
// -------------------------
// -------------------------
// handle case #3
// close active HAS_ATTRIBUTE on target branch when deleting
// -------------------------
CALL (n, a, src) {
    OPTIONAL MATCH (n)-[tgt:HAS_ATTRIBUTE {branch: $target_branch, status: "active"}]->(a)
    WHERE src.status = "deleted"
    AND tgt.to IS NULL
    SET tgt.to = $at, tgt.to_user_id = src.from_user_id
}
// -------------------------
// only remaining case to handle is #2, so we only care about active source HAS_ATTRIBUTE edges
// -------------------------
WITH n, a, src
WHERE src.status = "active"
// -------------------------
// the parent Node must be active on target/global branch to link an active HAS_ATTRIBUTE edge to it.
// Uses the LATEST IS_PART_OF edge and checks (status = "active" AND to IS NULL).
// -------------------------
CALL (n) {
    MATCH (n)-[ipo:IS_PART_OF]->(:Root)
    WHERE ipo.branch IN [$target_branch, $global_branch]
    RETURN (ipo.status = "active" AND ipo.to IS NULL) AS parent_is_active
    ORDER BY ipo.branch_level DESC, ipo.from DESC, ipo.status ASC
    LIMIT 1
}
WITH n, a, src, parent_is_active
WHERE parent_is_active = TRUE
// -------------------------
// create the active HAS_ATTRIBUTE edge on the target branch, if necessary
// -------------------------
CALL (n, a, src) {
    OPTIONAL MATCH (n)-[existing:HAS_ATTRIBUTE {branch: $target_branch, status: "active"}]->(a)
    WHERE existing.to IS NULL
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
// Merge IS_RELATED edges one side at a time: (Node)-[IS_RELATED]-(Relationship).
// Each IS_RELATED edge on the source branch is processed on its own. The other side of the
// Relationship is handled by a separate row. Orphan rel1/rel2 are prevented by the alive-peer
// check: an active create requires that some peer Node (different UUID than n) linked to the
// Relationship is alive on target.
//
// Relationships added-and-deleted on the source branch are handled by the `src.to IS NULL`
// filter: only the final-state edge (open) is picked up. For add+delete, only the trailing
// deleted edge matches — its close subquery finds nothing on target (relationship never
// existed there) and the status=active filter drops further processing. For delete+re-add
// of an existing relationship, only the trailing active edge matches — the create subquery
// finds the original active on target and skips creation.
// ==============================
MATCH (n:Node)-[src:IS_RELATED {branch: $source_branch}]-(rel:Relationship)
WHERE src.to IS NULL
AND rel.branch_support = "aware"
AND NOT n.uuid IN $excluded_uuids
// -------------------------
// No Node linked to this Relationship may be excluded
// a Relationship is only ever between 2 UUIDs, so no extra filtering is required
// -------------------------
AND NOT EXISTS {
    MATCH (rel)-[:IS_RELATED]-(linked:Node)
    WHERE linked.uuid IN $excluded_uuids
}
WITH n, rel, src,
    CASE WHEN startNode(src) = n THEN "r" ELSE "l" END AS dir,
    src.hierarchy AS hierarchy,
    src.from_user_id AS from_user_id,
    src.status AS status
// -------------------------
// Resolve the target-active sibling Node for this UUID. After a post-fork
// target-branch node-kind migration, target-branch writes must go on the
// currently-active sibling rather than the source-branch vertex. Falls back
// to ``n`` when no sibling is active on target.
// -------------------------
CALL (n) {
    OPTIONAL MATCH (tgt_candidate:Node {uuid: n.uuid})-[tgt_ipo:IS_PART_OF {branch: $target_branch, status: "active"}]->(:Root)
    WHERE tgt_ipo.to IS NULL
    WITH tgt_candidate, tgt_ipo
    ORDER BY tgt_ipo.from DESC
    LIMIT 1
    RETURN tgt_candidate
}
WITH n, rel, dir, hierarchy, from_user_id, status, COALESCE(tgt_candidate, n) AS tgt_n
// -------------------------
// Close active IS_RELATED on target branch between any sibling of ``n`` (same
// UUID) and ``rel``. UUID-scoping is needed so a branch-side delete closes the
// right edge regardless of whether the target-active sibling (for target
// migration) or the pre-migration sibling (source migration's pre-fork fixture
// edge) currently holds the active IS_RELATED.
// -------------------------
CALL (n, rel, status, from_user_id) {
    OPTIONAL MATCH (close_n:Node {uuid: n.uuid})-[tgt:IS_RELATED {branch: $target_branch, status: "active"}]-(rel)
    WHERE status = "deleted" AND tgt.to IS NULL
    SET tgt.to = $at, tgt.to_user_id = from_user_id
}
// -------------------------
// if we are deleting, then the work is done and we can filter to just active src edges for the more complex filtering below
// -------------------------
WITH n, rel, dir, hierarchy, from_user_id, status, tgt_n
WHERE status = "active"
// -------------------------
// For active edges, tgt_n must be alive on target (latest IS_PART_OF)
// -------------------------
CALL (tgt_n) {
    MATCH (tgt_n)-[ipo:IS_PART_OF]->(:Root)
    WHERE ipo.branch IN [$target_branch, $global_branch]
    RETURN (ipo.status = "active" AND ipo.to IS NULL) AS n_is_alive
    ORDER BY ipo.branch_level DESC, ipo.from DESC, ipo.status ASC
    LIMIT 1
}
WITH n, rel, dir, hierarchy, from_user_id, status, tgt_n, n_is_alive
WHERE n_is_alive = TRUE
// -------------------------
// For active edges, some peer Node (uuid != n.uuid, to treat migrated-kind old/new as same node)
// linked to the Relationship on source or target branch must be alive on target. The
// ``IS_RELATED`` side of the peer and the active ``IS_PART_OF`` side are resolved
// against UUID separately rather than the same vertex: under a target-branch node-kind
// migration the peer's IS_RELATED edge can live on the pre-migration sibling while the
// active IS_PART_OF lives on the post-migration sibling.
// -------------------------
CALL (n, rel) {
    OPTIONAL MATCH (peer:Node)-[peer_ir:IS_RELATED]-(rel)
    WHERE peer.uuid <> n.uuid
    AND peer_ir.branch IN [$source_branch, $target_branch]
    AND peer_ir.status = "active"
    AND peer_ir.to IS NULL
    WITH DISTINCT peer.uuid AS peer_uuid
    OPTIONAL MATCH (alive:Node {uuid: peer_uuid})-[p_ipo:IS_PART_OF]->(:Root)
    WHERE p_ipo.branch IN [$target_branch, $global_branch]
    AND p_ipo.status = "active"
    AND p_ipo.to IS NULL
    RETURN p_ipo IS NOT NULL AS has_alive_peer
    ORDER BY has_alive_peer DESC
    LIMIT 1
}
WITH n, rel, dir, hierarchy, from_user_id, status, tgt_n, has_alive_peer
WHERE has_alive_peer = TRUE
// -------------------------
// Create IS_RELATED with correct direction if not already present (anchors on
// ``tgt_n`` so the write lands on the target-active sibling)
// -------------------------
CALL (tgt_n, rel, dir, hierarchy, status, from_user_id) {
    WITH *
    WHERE dir = "r"
    OPTIONAL MATCH (tgt_n)-[existing_tgt:IS_RELATED {branch: $target_branch, status: "active"}]->(rel)
    WHERE existing_tgt.to IS NULL
    WITH tgt_n, rel, dir, hierarchy, status, from_user_id, existing_tgt
    WHERE existing_tgt IS NULL
    CREATE (tgt_n)-[:IS_RELATED {
        branch: $target_branch, branch_level: $branch_level, from: $at,
        status: status, hierarchy: hierarchy, from_user_id: from_user_id
    }]->(rel)
}
CALL (tgt_n, rel, dir, hierarchy, status, from_user_id) {
    WITH *
    WHERE dir = "l"
    OPTIONAL MATCH (tgt_n)<-[existing_tgt:IS_RELATED {branch: $target_branch, status: "active"}]-(rel)
    WHERE existing_tgt.to IS NULL
    WITH tgt_n, rel, dir, hierarchy, status, from_user_id, existing_tgt
    WHERE existing_tgt IS NULL
    CREATE (tgt_n)<-[:IS_RELATED {
        branch: $target_branch, branch_level: $branch_level, from: $at,
        status: status, hierarchy: hierarchy, from_user_id: from_user_id
    }]-(rel)
}
// -------------------------
// Set Relationship vertex metadata on first creation
// -------------------------
WITH rel, from_user_id
WHERE rel.created_at IS NULL
SET rel.created_at = $at, rel.created_by = from_user_id
        """
        self.add_to_query(query=query)


class BulkMergeAttributePropertyEdgesQuery(Query):
    """Bulk merge HAS_VALUE, IS_PROTECTED, HAS_OWNER, HAS_SOURCE edges that hang off Attribute vertices.

    These are singleton property edges: at most one active per parent per branch.
    When merging an active edge, close any existing active target edge pointing to a different child
    and create the new one. For active creates, the parent Node must be alive on target (based on
    the LATEST IS_PART_OF edge). For HAS_SOURCE / HAS_OWNER, the target child Node must also be alive.
    """

    name = "bulk_merge_attribute_property_edges"
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
// Attribute property edges: (Node)-[:HAS_ATTRIBUTE]->(Attribute)-[src]->(child)
// ==============================
MATCH (n:Node)-[:HAS_ATTRIBUTE]-(field:Attribute)-[src:HAS_VALUE|IS_PROTECTED|HAS_OWNER|HAS_SOURCE]->(child)
WHERE src.branch = $source_branch
AND src.to IS NULL
AND NOT n.uuid IN $excluded_uuids
AND field.branch_support = "aware"
WITH DISTINCT n, field, src, child,
    type(src) AS edge_type,
    src.status AS prop_status,
    src.from_user_id AS prop_from_user_id
// -------------------------
// Close any active target edge of same type from same field pointing to a different child
// (or the same child if this is a delete)
// -------------------------
CALL (field, child, edge_type, prop_status, prop_from_user_id) {
    OPTIONAL MATCH (field)-[tgt:$(edge_type)]->(other_child)
    WHERE tgt.branch = $target_branch
    AND tgt.status = "active"
    AND tgt.to IS NULL
    AND (other_child <> child OR prop_status = "deleted")
    SET tgt.to = $at, tgt.to_user_id = prop_from_user_id
}
// -------------------------
// For deleted edges, the work is done and we can filter to just active src edges
// -------------------------
WITH n, field, child, src, edge_type, prop_from_user_id
WHERE src.status = "active"
// -------------------------
// For active edges, the parent Node must be alive on target based on the latest IS_PART_OF
// -------------------------
CALL (n) {
    MATCH (n)-[ipo:IS_PART_OF]->(:Root)
    WHERE ipo.branch IN [$target_branch, $global_branch]
    RETURN (ipo.status = "active" AND ipo.to IS NULL) AS parent_is_alive
    ORDER BY ipo.branch_level DESC, ipo.from DESC, ipo.status ASC
    LIMIT 1
}
WITH n, field, child, src, edge_type, prop_from_user_id, parent_is_alive
WHERE parent_is_alive = TRUE
// -------------------------
// For HAS_SOURCE/HAS_OWNER active creates, the target child Node must also be alive on target
// -------------------------
CALL (child) {
    OPTIONAL MATCH (child)-[c_ipo:IS_PART_OF]->(:Root)
    WHERE c_ipo.branch IN [$target_branch, $global_branch]
    AND child:Node
    RETURN (c_ipo IS NULL OR (c_ipo.status = "active" AND c_ipo.to IS NULL)) AS child_is_alive
    ORDER BY c_ipo.branch_level DESC, c_ipo.from DESC, c_ipo.status ASC
    LIMIT 1
}
WITH field, child, src, edge_type, prop_from_user_id, child_is_alive
WHERE child_is_alive = TRUE
// -------------------------
// Create new property edge on target branch if not already present
// -------------------------
CALL (field, src, child, edge_type, prop_from_user_id) {
    OPTIONAL MATCH (field)-[existing {branch: $target_branch, status: "active"}]->(child)
    WHERE type(existing) = edge_type
    AND existing.to IS NULL
    WITH field, src, child, edge_type, prop_from_user_id, existing
    WHERE existing IS NULL
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


class BulkMergeRelationshipPropertyEdgesQuery(Query):
    """Bulk merge HAS_VALUE, IS_PROTECTED, HAS_OWNER, HAS_SOURCE edges that hang off Relationship vertices.

    For active creates: the owning Node `n` must be alive on target, AND some peer Node `p` connected
    to the same Relationship vertex must also be alive on target with an active IS_RELATED edge to
    the Relationship on the source or target branch. For HAS_SOURCE / HAS_OWNER, the target child
    Node must be alive too.
    """

    name = "bulk_merge_relationship_property_edges"
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
// Relationship property edges: (Node)-[:IS_RELATED]-(Relationship)-[src]->(child)
//
// Migrated-kind Nodes: for a migration A -> B, both the old vertex (A, marked deleted on source)
// and the new vertex (B, active on source) share the same Relationship vertex, so WITH DISTINCT
// can produce a row for each. The old vertex rows are dropped by the n-alive-on-target check
// (the old vertex has a deleted IS_PART_OF on target after merge). The new vertex rows proceed
// normally. For status=deleted src edges, both rows reach the close-subquery, but closing the
// same target edge twice is a no-op.
// ==============================
MATCH (n:Node)-[:IS_RELATED]-(field:Relationship)-[src:HAS_VALUE|IS_PROTECTED|HAS_OWNER|HAS_SOURCE]->(child)
WHERE src.branch = $source_branch
AND src.to IS NULL
AND NOT n.uuid IN $excluded_uuids
AND field.branch_support = "aware"
WITH DISTINCT n, field, src, child,
    type(src) AS edge_type,
    src.status AS prop_status,
    src.from_user_id AS prop_from_user_id
// -------------------------
// Close any active target edge of same type from same field pointing to a different child
// (or the same child if this is a delete)
// -------------------------
CALL (field, child, edge_type, prop_status, prop_from_user_id) {
    OPTIONAL MATCH (field)-[tgt:$(edge_type)]->(other_child)
    WHERE tgt.branch = $target_branch
    AND tgt.status = "active"
    AND tgt.to IS NULL
    AND (other_child <> child OR prop_status = "deleted")
    SET tgt.to = $at, tgt.to_user_id = prop_from_user_id
}
// -------------------------
// For deleted edges, the work is done and we can filter to just active src edges
// -------------------------
WITH n, field, child, src, edge_type, prop_from_user_id
WHERE src.status = "active"
// -------------------------
// For active edges, the owning Node n must be alive on target (latest IS_PART_OF)
// -------------------------
CALL (n) {
    MATCH (n)-[ipo:IS_PART_OF]->(:Root)
    WHERE ipo.branch IN [$target_branch, $global_branch]
    RETURN (ipo.status = "active" AND ipo.to IS NULL) AS n_is_alive
    ORDER BY ipo.branch_level DESC, ipo.from DESC, ipo.status ASC
    LIMIT 1
}
WITH n, field, child, src, edge_type, prop_from_user_id, n_is_alive
WHERE n_is_alive = TRUE
// -------------------------
// For active edges, some peer Node must be linked to the Relationship via an active IS_RELATED
// edge on the source or target branch, be alive on target (latest IS_PART_OF), and not be excluded.
// Use peer.uuid <> n.uuid so that migrated-kind/inheritance (old/new vertex with same UUID) is
// treated as the same node. There is at most one such peer per Relationship vertex, so the check
// is flattened to a single subquery that picks the latest IS_PART_OF directly.
// -------------------------
CALL (n, field) {
    OPTIONAL MATCH (peer:Node)-[peer_ir:IS_RELATED]-(field), (peer)-[p_ipo:IS_PART_OF]->(:Root)
    WHERE peer.uuid <> n.uuid
    AND peer_ir.branch IN [$source_branch, $target_branch]
    AND peer_ir.status = "active"
    AND peer_ir.to IS NULL
    AND NOT peer.uuid IN $excluded_uuids
    AND p_ipo.branch IN [$target_branch, $global_branch]
    RETURN (p_ipo IS NOT NULL AND p_ipo.status = "active" AND p_ipo.to IS NULL) AS has_alive_peer
    ORDER BY p_ipo.branch_level DESC, p_ipo.from DESC, p_ipo.status ASC
    LIMIT 1
}
WITH n, field, child, src, edge_type, prop_from_user_id, has_alive_peer
WHERE has_alive_peer = TRUE
// -------------------------
// For HAS_SOURCE/HAS_OWNER active creates, the target child Node must also be alive on target
// -------------------------
CALL (child) {
    OPTIONAL MATCH (child)-[c_ipo:IS_PART_OF]->(:Root)
    WHERE c_ipo.branch IN [$target_branch, $global_branch]
    AND child:Node
    RETURN (c_ipo IS NULL OR (c_ipo.status = "active" AND c_ipo.to IS NULL)) AS child_is_alive
    ORDER BY c_ipo.branch_level DESC, c_ipo.from DESC, c_ipo.status ASC
    LIMIT 1
}
WITH field, child, src, edge_type, prop_from_user_id, child_is_alive
WHERE child_is_alive = TRUE
// -------------------------
// Create new property edge on target branch if not already present
// -------------------------
CALL (field, src, child, edge_type, prop_from_user_id) {
    OPTIONAL MATCH (field)-[existing {branch: $target_branch, status: "active"}]->(child)
    WHERE type(existing) = edge_type
    AND existing.to IS NULL
    WITH field, src, child, edge_type, prop_from_user_id, existing
    WHERE existing IS NULL
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
