from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.diff.merger.exclusion_plan import (
        AttributePropertyPath,
        CardinalityOneDiffResolution,
        CarryOverBaseRelProperty,
        CarryOverDiffRelProperty,
        RelationshipPath,
        RelationshipPropertyPath,
    )
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
        excluded_node_uuids: list[str],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.at = at
        self.target_branch = target_branch
        self.source_branch_name = self.branch.name
        self.excluded_node_uuids = excluded_node_uuids

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "at": self.at.to_string(),
            "branch_level": self.target_branch.hierarchy_level,
            "target_branch": self.target_branch.name,
            "source_branch": self.source_branch_name,
            "global_branch": GLOBAL_BRANCH_NAME,
            "excluded_node_uuids": self.excluded_node_uuids,
        }
        query = """
// ==============================
// Phase 1: Merge IS_PART_OF edges (node existence)
// ==============================
MATCH (n:Node)-[src:IS_PART_OF]->(root:Root)
WHERE src.branch = $source_branch
AND src.to IS NULL
AND NOT n.uuid IN $excluded_node_uuids
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
// If the Node was migrated to a new kind/inheritance on the target branch,
// we need to identify the new target Node vertex
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
// close active IS_PART_OF on target branch when deleting
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
// (operates on ``tgt_n`` so the possible post-migration Node vertex's active sub-edges
// are closed)
// -------------------------
CALL (n, tgt_n, src) {
    WITH n, tgt_n, src
    WHERE src.status = "deleted"
    // ------------------------------
    // Only cascade if the UUID is truly deleted (no other vertex with an active IS_PART_OF
    // on the source branch). For migrated nodes on the source branch, the old vertex is "deleted"
    // but the new vertex, with the same UUID, is "active"
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
// ``WITH count(*) AS ...`` aggregates the prior rows into exactly one row, so
// phase 2 still runs when phase 1 produced zero matches
// ==============================
WITH count(*) AS _phase_separator
MATCH (n:Node)-[src:HAS_ATTRIBUTE]->(a:Attribute)
WHERE src.branch = $source_branch
AND src.to IS NULL
AND NOT n.uuid IN $excluded_node_uuids
AND a.branch_support = "aware"
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
// Uses the latest IS_PART_OF edge and checks (status = "active" AND to IS NULL).
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

    `excluded_relationship_paths` skips IS_RELATED edges for paths whose conflict was
    resolved to BASE

    Cardinality-one Relationship element conflict cleanup (`BulkMergeCardinalityOneResolutionQuery`)
    must run after this query.
    """

    name = "bulk_merge_relationship_edges"
    type = QueryType.WRITE
    insert_return = False
    raise_error_if_empty = False

    def __init__(
        self,
        at: Timestamp,
        target_branch: Branch,
        excluded_node_uuids: list[str],
        excluded_relationship_paths: list[RelationshipPath],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.at = at
        self.target_branch = target_branch
        self.source_branch_name = self.branch.name
        self.excluded_node_uuids = excluded_node_uuids
        self.excluded_relationship_paths = excluded_relationship_paths

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "at": self.at.to_string(),
            "branch_level": self.target_branch.hierarchy_level,
            "target_branch": self.target_branch.name,
            "source_branch": self.source_branch_name,
            "global_branch": GLOBAL_BRANCH_NAME,
            "excluded_node_uuids": self.excluded_node_uuids,
            "excluded_relationship_paths": [
                [p.node_uuid, p.relationship_identifier, p.peer_uuid] for p in self.excluded_relationship_paths
            ],
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
// existed there) and the status=active filter drops further processing
// ==============================
MATCH (n:Node)-[src:IS_RELATED {branch: $source_branch}]-(rel:Relationship)
WHERE src.to IS NULL
AND rel.branch_support = "aware"
AND NOT n.uuid IN $excluded_node_uuids
// -------------------------
// No Node linked to this Relationship may be excluded by node UUID
// a Relationship is only ever between 2 UUIDs, so no extra filtering is required
// -------------------------
AND NOT EXISTS {
    MATCH (rel)-[:IS_RELATED]-(linked:Node)
    WHERE linked.uuid IN $excluded_node_uuids
}
// -------------------------
// Skip paths whose Relationship-element conflict resolved to BASE. The check is symmetric so that
// both direction rows (n=A peer=B and n=B peer=A) are excluded by a single path entry.
// -------------------------
AND NOT EXISTS {
    MATCH (rel)-[:IS_RELATED]-(other:Node)
    WHERE other.uuid <> n.uuid
    AND (
        [n.uuid, rel.name, other.uuid] IN $excluded_relationship_paths
        OR [other.uuid, rel.name, n.uuid] IN $excluded_relationship_paths
    )
}
WITH n, rel, src,
    CASE WHEN startNode(src) = n THEN "r" ELSE "l" END AS dir,
    src.hierarchy AS hierarchy,
    src.from_user_id AS from_user_id,
    src.status AS status
// -------------------------
// Resolve the target-active sibling Node for this UUID. If the sibling Node had
// its kind/inheritance migrated on the target branch, this ensures we link to the
// correct Node vertex.
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
// If deleting, then close active IS_RELATED edges on target branch between any Node vertices
//with the same UUID and the ``rel`` vertex
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
    ORDER BY ipo.from DESC
    LIMIT 1
}
WITH n, rel, dir, hierarchy, from_user_id, status, tgt_n, n_is_alive
WHERE n_is_alive = TRUE
// -------------------------
// For active edges, some peer Node linked to the Relationship on source or target branch must be
// alive. Must filter by UUID and not vertex in case the peer Node had its kind/inheritance
// migrated on the target branch
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
// Create IS_RELATED with correct direction if not already present
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


class BulkMergeCardinalityOneResolutionQuery(Query):
    """Apply cardinality-one Relationship element conflict resolutions on top of the bulk IS_RELATED merge.

    Three concerns are handled in order:

    1. ``carry_over_base_relationship_properties`` DIFF element + BASE prop. Copies base's
       active prop edge from the displaced Relationship vertex onto the selected (source-side)
       Relationship-vertex before the displaced vertex is closed.
    2. ``carry_over_diff_relationship_properties`` BASE element + DIFF prop. Closes any
       existing same-type active edge on the kept (base-side) Relationship vertex; if source has an
       edge of that type, copies it onto the kept Relationship vertex.
    3. ``cardinality_one_diff_resolutions`` DIFF element. Closes every active edge
       (IS_RELATED + property edges) hanging off non-selected peer Relationship vertices on target,
       fully tearing down the displaced base-only Relationship vertex.

    Must run after `BulkMergeRelationshipEdgesQuery` (so the selected Relationship's IS_RELATED edges
    exist on target) and before `BulkMergeRelationshipPropertyEdgesQuery`. Internal block
    order matters: the carry-overs read base's active edges on the displaced Relationship that step 3
    then closes.
    """

    name = "bulk_merge_cardinality_one_resolution"
    type = QueryType.WRITE
    insert_return = False
    raise_error_if_empty = False

    def __init__(
        self,
        at: Timestamp,
        target_branch: Branch,
        cardinality_one_diff_resolutions: list[CardinalityOneDiffResolution],
        carry_over_base_relationship_properties: list[CarryOverBaseRelProperty],
        carry_over_diff_relationship_properties: list[CarryOverDiffRelProperty],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.at = at
        self.target_branch = target_branch
        self.source_branch_name = self.branch.name
        self.cardinality_one_diff_resolutions = cardinality_one_diff_resolutions
        self.carry_over_base_relationship_properties = carry_over_base_relationship_properties
        self.carry_over_diff_relationship_properties = carry_over_diff_relationship_properties

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "at": self.at.to_string(),
            "branch_level": self.target_branch.hierarchy_level,
            "target_branch": self.target_branch.name,
            "source_branch": self.source_branch_name,
            "cardinality_one_diff_resolutions": [
                [p.node_uuid, p.relationship_identifier, p.selected_peer_uuid]
                for p in self.cardinality_one_diff_resolutions
            ],
            "carry_over_base_relationship_properties": [
                [p.node_uuid, p.relationship_identifier, p.selected_peer_uuid, p.edge_type]
                for p in self.carry_over_base_relationship_properties
            ],
            "carry_over_diff_relationship_properties": [
                [p.node_uuid, p.relationship_identifier, p.kept_peer_uuid, p.source_peer_uuid, p.edge_type]
                for p in self.carry_over_diff_relationship_properties
            ],
        }

        query = """
// ==============================
// Step 1: Carry-over (DIFF element + BASE prop). Base's property edge lives on the
// displaced Relationship vertex and would be lost when that vertex is closed in step 3. Copy
// it onto the selected (source-side) Relationship vertex first.
// ==============================
// ------------------------------
// Use a subquery so the next steps still run when the param list is empty.
// ------------------------------
CALL () {
    UNWIND $carry_over_base_relationship_properties AS carry
    WITH carry[0] AS node_uuid, carry[1] AS rel_name, carry[2] AS selected_peer_uuid, carry[3] AS edge_type
    // ------------------------------
    // Match the selected (source-side) Relationship-vertex first. Use it to determine the
    // direction of the Relationship
    // ------------------------------
    MATCH (carry_n:Node {uuid: node_uuid})
        -[s_ir1:IS_RELATED {branch: $target_branch, status: "active"}]-(selected_rel:Relationship {name: rel_name})
        -[s_ir2:IS_RELATED {branch: $target_branch, status: "active"}]-(:Node {uuid: selected_peer_uuid})
    WHERE s_ir1.to IS NULL AND s_ir2.to IS NULL
    WITH carry_n, selected_rel, edge_type, selected_peer_uuid, rel_name,
        CASE
            WHEN startNode(s_ir1) = carry_n AND startNode(s_ir2) = selected_rel THEN "outbound"
            WHEN endNode(s_ir1) = carry_n AND endNode(s_ir2) = selected_rel THEN "inbound"
            ELSE "bidir"
        END AS direction
    // ------------------------------
    // Match the displaced (base-side) Relationship-vertex using the direction
    // ------------------------------
    MATCH (carry_n)
        -[d_ir1:IS_RELATED {branch: $target_branch, status: "active"}]-(displaced_rel:Relationship {name: rel_name})
        -[d_ir2:IS_RELATED {branch: $target_branch, status: "active"}]-(displaced_peer:Node)
    WHERE displaced_peer.uuid <> selected_peer_uuid
    AND d_ir1.to IS NULL AND d_ir2.to IS NULL
    AND displaced_rel <> selected_rel
    AND (
        (direction = "outbound" AND startNode(d_ir1) = carry_n AND startNode(d_ir2) = displaced_rel)
        OR (direction = "inbound" AND endNode(d_ir1) = carry_n AND endNode(d_ir2) = displaced_rel)
        OR direction = "bidir"
    )
    // ------------------------------
    // The active+to-IS-NULL filter naturally short-circuits this carry-over when base's
    // resolution is a delete b/c there is no active edge to copy, so the MATCH does not find an edge
    // ------------------------------
    MATCH (displaced_rel)-[target_e:$(edge_type) {branch: $target_branch, status: "active"}]->(child)
    WHERE target_e.to IS NULL
    WITH DISTINCT edge_type, selected_rel, target_e, child
    CREATE (selected_rel)-[new_e:$(edge_type)]->(child)
    SET new_e = properties(target_e)
    SET new_e.branch = $target_branch, new_e.branch_level = $branch_level, new_e.from = $at, new_e.to = NULL, new_e.to_user_id = NULL
}

// ==============================
// Step 2: Inverse carry-over (BASE peer + DIFF prop). Source's property edge lives on
// the source-side Relationship-vertex (which is excluded from the merge). Apply source's value to
// the kept (base-side) Relationship-vertex, and close any pre-existing same-type active edge on
// the kept Relationship.
// ==============================
WITH 1 AS _carry_over_diff_separator
LIMIT 1
CALL () {
    UNWIND $carry_over_diff_relationship_properties AS carry
    WITH carry[0] AS node_uuid, carry[1] AS rel_name, carry[2] AS kept_peer_uuid,
         carry[3] AS source_peer_uuid, carry[4] AS edge_type
    // ------------------------------
    // Match source's Relationship-vertex (anchored by `source_peer_uuid`) to find source's
    // active prop edge. The source-side Relationship-vertex was excluded from the bulk merge,
    // so its IS_RELATED edges and prop edges live on $source_branch only.
    // ------------------------------
    OPTIONAL MATCH (:Node {uuid: node_uuid})
        -[s_ir1:IS_RELATED {branch: $source_branch, status: "active"}]-(source_rel:Relationship {name: rel_name})
        -[s_ir2:IS_RELATED {branch: $source_branch, status: "active"}]-(:Node {uuid: source_peer_uuid})
    WHERE s_ir1.to IS NULL AND s_ir2.to IS NULL
    OPTIONAL MATCH (source_rel)-[src_e:$(edge_type) {branch: $source_branch, status: "active"}]->(child)
    WHERE src_e.to IS NULL
    // ------------------------------
    // Match the kept (base-side) Relationship-vertex (anchored by `kept_peer_uuid`).
    // IS_RELATED edges are filtered to the active target-branch path and this is only for
    // a cardinality-one relationship, so we can assume a single Relationship vertex.
    // ------------------------------
    MATCH (:Node {uuid: node_uuid})
        -[k_ir1:IS_RELATED {branch: $target_branch, status: "active"}]-(kept_rel:Relationship {name: rel_name})
        -[k_ir2:IS_RELATED {branch: $target_branch, status: "active"}]-(:Node {uuid: kept_peer_uuid})
    WHERE k_ir1.to IS NULL AND k_ir2.to IS NULL
    WITH DISTINCT edge_type, kept_rel, src_e, child, src_e.from_user_id AS source_user_id
    // ------------------------------
    // Step 2a: always close any existing same-type active edge on the kept Relationship.
    // The DIFF resolution wins regardless of whether source UPDATED/ADDED or REMOVED the
    // prop, so this close runs even when there is no src_e to copy.
    // ------------------------------
    CALL (kept_rel, edge_type, source_user_id) {
        OPTIONAL MATCH (kept_rel)-[existing_e:$(edge_type) {branch: $target_branch, status: "active"}]->()
        WHERE existing_e.to IS NULL
        SET existing_e.to = $at, existing_e.to_user_id = source_user_id
    }
    // ------------------------------
    // Step 2b: if source has an active edge of this type, copy it to the kept Relationship.
    // ------------------------------
    WITH edge_type, kept_rel, src_e, child
    WHERE src_e IS NOT NULL AND child IS NOT NULL
    CREATE (kept_rel)-[new_e:$(edge_type)]->(child)
    SET new_e = properties(src_e)
    SET new_e.branch = $target_branch, new_e.branch_level = $branch_level, new_e.from = $at, new_e.to = NULL, new_e.to_user_id = NULL
}

// ==============================
// Step 3: Cardinality-one DIFF resolutions. Source's IS_RELATED edge to the selected peer
// was already created by `BulkMergeRelationshipEdgesQuery`. Close every active edge
// hanging off any *other-peer* Relationship vertex on target so the dead target-branch
// Relationship vertex is fully torn down.
// ==============================
WITH 1 AS _extra_close_separator
LIMIT 1
UNWIND $cardinality_one_diff_resolutions AS resolution
WITH resolution[0] AS node_uuid, resolution[1] AS rel_name, resolution[2] AS selected_peer_uuid
// ------------------------------
// Match the selected peer's Relationship-vertex to determine direction.
// Expects that source's IS_RELATED edges have already been propagated to target branch.
// ------------------------------
MATCH (n:Node {uuid: node_uuid})
    -[sel_ir1:IS_RELATED {branch: $target_branch, status: "active"}]-(sel_rel:Relationship {name: rel_name})
    -[sel_ir2:IS_RELATED {branch: $target_branch, status: "active"}]-(:Node {uuid: selected_peer_uuid})
WHERE sel_ir1.to IS NULL AND sel_ir2.to IS NULL
// `source_user_id` attributes the close on the displaced rel-vertex below to source's user
// — the close is driven by source's DIFF-resolved peer change, and source's IS_RELATED
// edge on target carries the source-side user who triggered it.
WITH n, node_uuid, rel_name, selected_peer_uuid, sel_ir1.from_user_id AS source_user_id,
    CASE
        WHEN startNode(sel_ir1) = n AND startNode(sel_ir2) = sel_rel THEN "outbound"
        WHEN endNode(sel_ir1) = n AND endNode(sel_ir2) = sel_rel THEN "inbound"
        ELSE "bidir"
    END AS direction
OPTIONAL MATCH (n)-[ir1:IS_RELATED {branch: $target_branch, status: "active"}]-
    (rel:Relationship {name: rel_name})-[ir2:IS_RELATED {branch: $target_branch, status: "active"}]-(other:Node)
WHERE other.uuid <> selected_peer_uuid
AND ir1.to IS NULL
AND ir2.to IS NULL
AND (
    (direction = "outbound" AND startNode(ir1) = n AND startNode(ir2) = rel)
    OR (direction = "inbound" AND endNode(ir1) = n AND endNode(ir2) = rel)
    OR direction = "bidir"
)
SET ir1.to = $at, ir1.to_user_id = source_user_id, ir2.to = $at, ir2.to_user_id = source_user_id
WITH DISTINCT rel, source_user_id
WHERE rel IS NOT NULL
CALL (rel, source_user_id) {
    OPTIONAL MATCH (rel)-[prop_e:HAS_VALUE|IS_PROTECTED|HAS_OWNER|HAS_SOURCE {branch: $target_branch, status: "active"}]->()
    WHERE prop_e.to IS NULL
    SET prop_e.to = $at, prop_e.to_user_id = source_user_id
}
        """
        self.add_to_query(query=query)


class BulkMergeAttributePropertyEdgesQuery(Query):
    """Bulk merge HAS_VALUE, IS_PROTECTED, HAS_OWNER, HAS_SOURCE edges that hang off Attribute vertices.

    These are singleton property edges: at most one active per parent per branch.
    When merging an active edge, close any existing active target edge pointing to a different child
    and create the new one. For active creates, the parent Node must be alive on target (based on
    the LATEST IS_PART_OF edge). For HAS_SOURCE / HAS_OWNER, the target child Node must also be alive.

    `excluded_attribute_property_paths` skips specific (node_uuid, attr_name, edge_type) paths whose
    property conflict was resolved to BASE.
    """

    name = "bulk_merge_attribute_property_edges"
    type = QueryType.WRITE
    insert_return = False
    raise_error_if_empty = False

    def __init__(
        self,
        at: Timestamp,
        target_branch: Branch,
        excluded_node_uuids: list[str],
        excluded_attribute_property_paths: list[AttributePropertyPath],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.at = at
        self.target_branch = target_branch
        self.source_branch_name = self.branch.name
        self.excluded_node_uuids = excluded_node_uuids
        self.excluded_attribute_property_paths = excluded_attribute_property_paths

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "at": self.at.to_string(),
            "branch_level": self.target_branch.hierarchy_level,
            "target_branch": self.target_branch.name,
            "source_branch": self.source_branch_name,
            "global_branch": GLOBAL_BRANCH_NAME,
            "excluded_node_uuids": self.excluded_node_uuids,
            "excluded_attribute_property_paths": [
                [p.node_uuid, p.attribute_name, p.edge_type] for p in self.excluded_attribute_property_paths
            ],
        }
        query = """
// ==============================
// Attribute property edges: (Node)-[:HAS_ATTRIBUTE]->(Attribute)-[src]->(child)
// ==============================
MATCH (n:Node)-[:HAS_ATTRIBUTE]-(field:Attribute)-[src:HAS_VALUE|IS_PROTECTED|HAS_OWNER|HAS_SOURCE]->(child)
WHERE src.branch = $source_branch
AND src.to IS NULL
AND NOT n.uuid IN $excluded_node_uuids
AND NOT [n.uuid, field.name, type(src)] IN $excluded_attribute_property_paths
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
    ORDER BY ipo.from DESC
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
    ORDER BY c_ipo.from DESC
    LIMIT 1
}
WITH field, child, src, edge_type, prop_from_user_id, child_is_alive
WHERE child_is_alive = TRUE
// -------------------------
// Create new property edge on target branch if not already present
// -------------------------
CALL (field, src, child, edge_type, prop_from_user_id) {
    OPTIONAL MATCH (field)-[existing:$(edge_type) {branch: $target_branch, status: "active"}]->(child)
    WHERE existing.to IS NULL
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

    Exclusions:
    - `excluded_relationship_paths` skips ALL property edges hanging off Relationship vertices for paths
      whose Relationship-element conflict was resolved to BASE.
    - `excluded_relationship_property_paths` skips a specific (node_uuid, rel_id, peer_uuid, edge_type)
      whose property conflict was resolved to BASE.
    Both checks are symmetric so the n-side and peer-side rows of the same Relationship vertex
    are excluded by a single path entry.
    """

    name = "bulk_merge_relationship_property_edges"
    type = QueryType.WRITE
    insert_return = False
    raise_error_if_empty = False

    def __init__(
        self,
        at: Timestamp,
        target_branch: Branch,
        excluded_node_uuids: list[str],
        excluded_relationship_paths: list[RelationshipPath],
        excluded_relationship_property_paths: list[RelationshipPropertyPath],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.at = at
        self.target_branch = target_branch
        self.source_branch_name = self.branch.name
        self.excluded_node_uuids = excluded_node_uuids
        self.excluded_relationship_paths = excluded_relationship_paths
        self.excluded_relationship_property_paths = excluded_relationship_property_paths

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "at": self.at.to_string(),
            "branch_level": self.target_branch.hierarchy_level,
            "target_branch": self.target_branch.name,
            "source_branch": self.source_branch_name,
            "global_branch": GLOBAL_BRANCH_NAME,
            "excluded_node_uuids": self.excluded_node_uuids,
            "excluded_relationship_paths": [
                [p.node_uuid, p.relationship_identifier, p.peer_uuid] for p in self.excluded_relationship_paths
            ],
            "excluded_relationship_property_paths": [
                [p.node_uuid, p.relationship_identifier, p.peer_uuid, p.edge_type]
                for p in self.excluded_relationship_property_paths
            ],
        }
        query = """
// ==============================
// Relationship property edges: (Node)-[:IS_RELATED]-(Relationship)-[src]->(child)
// ==============================
MATCH (n:Node)-[:IS_RELATED]-(field:Relationship)-[src:HAS_VALUE|IS_PROTECTED|HAS_OWNER|HAS_SOURCE]->(child)
WHERE src.branch = $source_branch
AND src.to IS NULL
AND NOT n.uuid IN $excluded_node_uuids
AND field.branch_support = "aware"
// -------------------------
// Skip Relationship vertices to is exclude. Symmetric so both n-side and peer-side rows are filtered.
// -------------------------
AND NOT EXISTS {
    MATCH (field)-[:IS_RELATED]-(other:Node)
    WHERE other.uuid <> n.uuid
    AND (
        [n.uuid, field.name, other.uuid] IN $excluded_relationship_paths
        OR [other.uuid, field.name, n.uuid] IN $excluded_relationship_paths
    )
}
// -------------------------
// Skip specific property paths whose property conflict resolved to BASE. Symmetric for the
// same reason as above.
// -------------------------
AND NOT EXISTS {
    MATCH (field)-[:IS_RELATED]-(other:Node)
    WHERE other.uuid <> n.uuid
    AND (
        [n.uuid, field.name, other.uuid, type(src)] IN $excluded_relationship_property_paths
        OR [other.uuid, field.name, n.uuid, type(src)] IN $excluded_relationship_property_paths
    )
}
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
    ORDER BY ipo.from DESC
    LIMIT 1
}
WITH n, field, child, src, edge_type, prop_from_user_id, n_is_alive
WHERE n_is_alive = TRUE
// -------------------------
// Find the active peer Node vertex. Filter by UUID to account for Nodes that had
// their kind/inheritance migrated on target branch
// -------------------------
CALL (n, field) {
    OPTIONAL MATCH (peer:Node)-[peer_ir:IS_RELATED]-(field), (peer)-[p_ipo:IS_PART_OF]->(:Root)
    WHERE peer.uuid <> n.uuid
    AND peer_ir.branch IN [$source_branch, $target_branch]
    AND peer_ir.status = "active"
    AND peer_ir.to IS NULL
    AND NOT peer.uuid IN $excluded_node_uuids
    AND p_ipo.branch IN [$target_branch, $global_branch]
    RETURN (p_ipo IS NOT NULL AND p_ipo.status = "active" AND p_ipo.to IS NULL) AS has_alive_peer
    ORDER BY p_ipo.from DESC
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
    ORDER BY c_ipo.from DESC
    LIMIT 1
}
WITH field, child, src, edge_type, prop_from_user_id, child_is_alive
WHERE child_is_alive = TRUE
// -------------------------
// Create new property edge on target branch if not already present
// -------------------------
CALL (field, src, child, edge_type, prop_from_user_id) {
    OPTIONAL MATCH (field)-[existing:$(edge_type) {branch: $target_branch, status: "active"}]->(child)
    WHERE existing.to IS NULL
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
