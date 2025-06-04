from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from infrahub.core.constants import RelationshipDirection
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.query import Query, QueryType
from infrahub.log import get_logger

from ..shared import ArbitraryMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

log = get_logger()


class CleanUpDuplicatedUuidVertices(Query):
    """
    Find vertexes that include the given label and have the same UUID and same set of labels
    For each of these duplicate vertex groups, keep one and mark all the others to be deleted by the PerformHardDeletesQuery
      - Group all of the edges touching a vertex in this vertex group by branch, edge_type, peer_element_id, and direction
        - For each edge group, we will link one edge to the vertex we are keeping for this vertex group and mark all of the others to be deleted
        - we will set/create one active edge from the vertex to keep to the peer of this group, setting its from time to the earliest active
            from time in this group
        - if ALL edges in this edge group are deleted, then we will set the to time of the active edge to the latest deleted time and
            set/create a deleted edge with a from time of the latest deleted time
    """

    name = "clean_up_duplicated_uuid_vertices"
    type = QueryType.WRITE
    insert_return = False
    insert_limit = False

    def __init__(
        self,
        vertex_label: str,
        outbound_edge_types: list[DatabaseEdgeType],
        inbound_edge_types: list[DatabaseEdgeType],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.vertex_label = vertex_label
        self.outbound_edge_types = outbound_edge_types
        self.inbound_edge_types = inbound_edge_types

    def _get_or_create_active_edge_subquery(
        self,
        edge_type: DatabaseEdgeType,
        direction: Literal[RelationshipDirection.INBOUND, RelationshipDirection.OUTBOUND],
    ) -> str:
        if direction is RelationshipDirection.INBOUND:
            l_arrow = "<"
            r_arrow = ""
        else:
            l_arrow = ""
            r_arrow = ">"

        query = """
    CALL {
        // ------------
        // get or create the active %(edge_type)s edge
        // ------------
        WITH vertex_to_keep, edge_type, branch, peer, earliest_active_time, latest_deleted_time, all_edges_deleted, edge_to_copy
        WITH vertex_to_keep, edge_type, branch, peer, earliest_active_time, latest_deleted_time, all_edges_deleted, edge_to_copy
        WHERE edge_type = "%(edge_type)s"
        MERGE (vertex_to_keep)%(l_arrow)s-[active_edge:%(edge_type)s {branch: branch, status: "active"}]-%(r_arrow)s(peer)
        WITH active_edge, edge_to_copy, earliest_active_time, latest_deleted_time, all_edges_deleted
        LIMIT 1
        SET active_edge.to_delete = NULL
        SET active_edge.from = earliest_active_time
        SET active_edge.to = CASE
            WHEN all_edges_deleted = TRUE THEN latest_deleted_time
            ELSE NULL
        END
        SET active_edge.branch_level = edge_to_copy.branch_level
        SET active_edge.hierarchy = edge_to_copy.hierarchy
    }
        """ % {
            "edge_type": edge_type.value,
            "l_arrow": l_arrow,
            "r_arrow": r_arrow,
        }
        return query

    def _add_deleted_edge_subquery(
        self,
        edge_type: DatabaseEdgeType,
        direction: Literal[RelationshipDirection.INBOUND, RelationshipDirection.OUTBOUND],
    ) -> str:
        if direction is RelationshipDirection.INBOUND:
            l_arrow = "<"
            r_arrow = ""
        else:
            l_arrow = ""
            r_arrow = ">"
        subquery = """
    CALL {
        // ------------
        // create the deleted %(edge_type)s edge
        // ------------
        WITH vertex_to_keep, edge_type, branch, peer, latest_deleted_time, edge_to_copy
        WITH vertex_to_keep, edge_type, branch, peer, latest_deleted_time, edge_to_copy
        WHERE edge_type = "%(edge_type)s"
        MERGE (vertex_to_keep)%(l_arrow)s-[deleted_edge:%(edge_type)s {branch: branch, status: "deleted"}]-%(r_arrow)s(peer)
        WITH deleted_edge, latest_deleted_time, edge_to_copy
        LIMIT 1
        SET deleted_edge.to_delete = NULL
        SET deleted_edge.from = latest_deleted_time
        SET deleted_edge.to = NULL
        SET deleted_edge.branch_level = edge_to_copy.branch_level
        SET deleted_edge.hierarchy = edge_to_copy.hierarchy
    }
        """ % {"edge_type": edge_type.value, "l_arrow": l_arrow, "r_arrow": r_arrow}
        return subquery

    def _build_directed_edges_subquery(
        self,
        db: InfrahubDatabase,
        direction: Literal[RelationshipDirection.INBOUND, RelationshipDirection.OUTBOUND],
        edge_types: list[DatabaseEdgeType],
    ) -> str:
        if direction is RelationshipDirection.INBOUND:
            l_arrow = "<"
            r_arrow = ""
        else:
            l_arrow = ""
            r_arrow = ">"
        active_subqueries: list[str] = []
        delete_subqueries: list[str] = []
        for edge_type in edge_types:
            active_subqueries.append(
                self._get_or_create_active_edge_subquery(
                    edge_type=edge_type,
                    direction=direction,
                )
            )
            delete_subqueries.append(self._add_deleted_edge_subquery(edge_type=edge_type, direction=direction))
        active_edge_subqueries = "\n".join(active_subqueries)
        deleted_edge_subqueries = "\n".join(delete_subqueries)

        edges_query = """
//------------
// Get every %(direction)s branch, edge_type, peer element_id combinations touching vertices with this uuid/labels combination
//------------
CALL {
    WITH n_uuid, vertex_element_ids, element_id_to_keep
    CALL {
        WITH n_uuid, vertex_element_ids
        MATCH (n:%(vertex_label)s {uuid: n_uuid})
        WHERE %(id_func_name)s(n) IN vertex_element_ids
        MATCH (n)%(l_arrow)s-[e]-%(r_arrow)s(peer)
        WITH DISTINCT e.branch AS branch, type(e) AS edge_type, %(id_func_name)s(peer) AS peer_element_id
        RETURN branch, edge_type, peer_element_id
    }
    //------------
    // Are all of the edges with these with this branch/edge_type/peer_element_id combination deleted?
    //------------
    CALL {
        WITH n_uuid, vertex_element_ids, branch, edge_type, peer_element_id
        // nodes with this edge_type/branch/peer combo
        MATCH (node_with_edge:%(vertex_label)s {uuid: n_uuid})%(l_arrow)s-[e {branch: branch}]-%(r_arrow)s(peer)
        WHERE %(id_func_name)s(node_with_edge) IN vertex_element_ids
        AND type(e) = edge_type
        AND %(id_func_name)s(peer) = peer_element_id
        // count of nodes with this edge_type/branch/peer combo
        WITH DISTINCT n_uuid, branch, edge_type, peer_element_id, %(id_func_name)s(node_with_edge) AS node_with_edge_element_id
        WITH n_uuid, branch, edge_type, peer_element_id, collect(node_with_edge_element_id) AS node_with_edge_element_ids
        // nodes with this edge_type/branch/peer combo where the edge is DELETED
        OPTIONAL MATCH (node_with_deleted_edge:%(vertex_label)s {uuid: n_uuid})%(l_arrow)s-[e {branch: branch}]-%(r_arrow)s(peer)
        WHERE %(id_func_name)s(node_with_deleted_edge) IN node_with_edge_element_ids
        AND type(e) = edge_type
        AND %(id_func_name)s(peer) = peer_element_id
        AND (e.status = "deleted" OR e.to IS NOT NULL)
        // count of nodes with this DELETED edge_type/branch/peer combo
        WITH DISTINCT node_with_edge_element_ids, %(id_func_name)s(node_with_deleted_edge) AS node_with_deleted_edge_element_id
        WITH node_with_edge_element_ids, collect(node_with_deleted_edge_element_id) AS node_with_deleted_edge_element_ids
        RETURN size(node_with_edge_element_ids) = size(node_with_deleted_edge_element_ids) AS all_edges_deleted
    }
    //------------
    // What is the earliest active time for this branch/edge_type/peer_element_id/UUID/labels combination?
    //------------
    CALL {
        WITH n_uuid, vertex_element_ids, branch, edge_type, peer_element_id
        MATCH (n {uuid: n_uuid})%(l_arrow)s-[e {branch: branch, status: "active"}]-%(r_arrow)s(peer)
        WHERE %(id_func_name)s(n) IN vertex_element_ids
        AND type(e) = edge_type
        AND %(id_func_name)s(peer) = peer_element_id
        RETURN e.from AS earliest_active_time
        ORDER BY e.from ASC
        LIMIT 1
    }
    //------------
    // What is the latest deleted time for this branch/edge_type/peer_element_id/UUID/labels combination?
    //------------
    CALL {
        WITH n_uuid, vertex_element_ids, branch, edge_type, peer_element_id, all_edges_deleted
        OPTIONAL MATCH (n {uuid: n_uuid})%(l_arrow)s-[e {branch: branch}]-%(r_arrow)s(peer)
        WHERE all_edges_deleted = TRUE
        AND %(id_func_name)s(n) IN vertex_element_ids
        AND type(e) = edge_type
        AND %(id_func_name)s(peer) = peer_element_id
        RETURN CASE
            WHEN e.status = "active" THEN e.to
            ELSE e.from
        END AS latest_deleted_time
        ORDER BY latest_deleted_time DESC
        LIMIT 1
    }
    // ------------
    // Add the %(direction)s edges to the node we are keeping, if necessary
    // ------------
    CALL {
        WITH n_uuid, vertex_element_ids, element_id_to_keep, branch, edge_type, peer_element_id, all_edges_deleted,
            earliest_active_time, latest_deleted_time
        // get the node we are keeping
        MATCH (vertex_to_keep {uuid: n_uuid})
        WHERE %(id_func_name)s(vertex_to_keep) = element_id_to_keep
        // get the peer we are linking to
        MATCH (n {uuid: n_uuid})%(l_arrow)s-[]-%(r_arrow)s(peer)
        WHERE %(id_func_name)s(n) IN vertex_element_ids
        AND %(id_func_name)s(peer) = peer_element_id
        WITH n_uuid, vertex_element_ids, element_id_to_keep, vertex_to_keep, branch, edge_type, peer, all_edges_deleted,
            earliest_active_time, latest_deleted_time
        LIMIT 1
        // ------------
        // mark all other edges for this branch/edge_type/peer combination as to be deleted
        // we will unmark any to keep later
        // ------------
        CALL {
            WITH n_uuid, branch, peer, vertex_element_ids, edge_type
            OPTIONAL MATCH (n {uuid: n_uuid})%(l_arrow)s-[edge_to_delete {branch: branch}]-%(r_arrow)s(peer)
            WHERE %(id_func_name)s(n) IN vertex_element_ids
            AND type(edge_to_delete) = edge_type
            SET edge_to_delete.to_delete = TRUE
        }
        CALL {
            // ------------
            // get the edge to copy
            // ------------
            WITH n_uuid, branch, vertex_element_ids, edge_type, peer
            MATCH (n {uuid: n_uuid})%(l_arrow)s-[e {branch: branch, status: "active"}]-%(r_arrow)s(peer)
            WHERE %(id_func_name)s(n) IN vertex_element_ids
            AND type(e) = edge_type
            RETURN e AS edge_to_copy
            ORDER BY e.from DESC
            LIMIT 1
        }
        %(active_edge_subqueries)s
        // ------------
        // conditionally create the deleted edges
        // ------------
        WITH n_uuid, vertex_element_ids, vertex_to_keep, branch, edge_type, peer, all_edges_deleted,
            latest_deleted_time, edge_to_copy
        WHERE all_edges_deleted = TRUE
        %(deleted_edge_subqueries)s
    }
}
        """ % {
            "direction": direction.value,
            "l_arrow": l_arrow,
            "r_arrow": r_arrow,
            "id_func_name": db.get_id_function_name(),
            "active_edge_subqueries": active_edge_subqueries,
            "deleted_edge_subqueries": deleted_edge_subqueries,
            "vertex_label": self.vertex_label,
        }
        return edges_query

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params["limit"] = self.limit or 1000
        self.params["offset"] = self.offset or 0
        query_start = """
//------------
// Find vertices with the same labels and UUID
//------------
MATCH (n:%(vertex_label)s)
WITH n.uuid AS node_uuid, count(*) as num_nodes_with_uuid
WHERE num_nodes_with_uuid > 1
WITH DISTINCT node_uuid
ORDER BY node_uuid ASC
MATCH (n:%(vertex_label)s {uuid: node_uuid})
WITH node_uuid, n, %(id_func_name)s(n) AS element_id
ORDER BY node_uuid ASC, element_id ASC
CALL {
    WITH n
    WITH labels(n) AS n_labels
    UNWIND n_labels AS n_label
    WITH n_label
    ORDER BY n_label ASC
    RETURN collect(n_label) AS sorted_labels
}
WITH n.uuid AS n_uuid, sorted_labels, collect(element_id) AS vertex_element_ids
WHERE size(vertex_element_ids) > 1
WITH n_uuid, vertex_element_ids
//------------
// Are there more nodes to process after this query?
//------------
WITH collect([n_uuid, vertex_element_ids]) AS duplicate_details
WITH duplicate_details, size(duplicate_details) > ($offset + $limit) AS more_nodes_to_process
UNWIND duplicate_details AS duplicate_detail
WITH duplicate_detail[0] AS n_uuid, duplicate_detail[1] AS vertex_element_ids, more_nodes_to_process
//------------
// Limit the nodes to process
//------------
SKIP $offset
LIMIT $limit
//------------
// Which node are we going to keep for this UUID/labels combination?
//------------
CALL {
    WITH vertex_element_ids
    UNWIND vertex_element_ids AS element_id
    WITH element_id
    ORDER BY element_id ASC
    RETURN element_id AS element_id_to_keep
    LIMIT 1
}
        """ % {"id_func_name": db.get_id_function_name(), "vertex_label": self.vertex_label}
        self.add_to_query(query_start)

        if self.outbound_edge_types:
            outbound_edges_query = self._build_directed_edges_subquery(
                db=db,
                direction=RelationshipDirection.OUTBOUND,
                edge_types=self.outbound_edge_types,
            )
            self.add_to_query(outbound_edges_query)
        if self.inbound_edge_types:
            inbound_edges_query = self._build_directed_edges_subquery(
                db=db,
                direction=RelationshipDirection.INBOUND,
                edge_types=self.inbound_edge_types,
            )
            self.add_to_query(inbound_edges_query)

        query_end = """
// ------------
// Mark the nodes to delete
// ------------
MATCH (node_to_delete:%(vertex_label)s {uuid: n_uuid})
WHERE %(id_func_name)s(node_to_delete) IN vertex_element_ids
AND %(id_func_name)s(node_to_delete) <> element_id_to_keep
SET node_to_delete.to_delete = TRUE
RETURN more_nodes_to_process
        """ % {"id_func_name": db.get_id_function_name(), "vertex_label": self.vertex_label}
        self.add_to_query(query_end)
        self.return_labels = ["more_nodes_to_process"]


class DeleteDuplicatedEdgesQuery(Query):
    """
    For all Node vertices, find duplicated or overlapping edges of the same status, type, direction, and branch to update and delete
    - one edge will be kept for each pair of nodes and a given status, type, direction, and branch. it will be
        updated to have the earliest "from" and latest "to" times in this group
    - all the other duplicate/overlapping edges will be deleted
    """

    name = "delete_duplicated_edges"
    type = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
// ------------
// Find vertex pairs that have duplicate edges
// ------------
MATCH (node_with_dup_edges:Node)-[edge]-(peer)
WITH
    node_with_dup_edges,
    type(edge) AS edge_type,
    edge.status AS edge_status,
    edge.branch AS edge_branch,
    peer,
    %(id_func_name)s(startNode(edge)) = %(id_func_name)s(node_with_dup_edges) AS is_outbound
WITH node_with_dup_edges, edge_type, edge_status, edge_branch, peer, is_outbound, count(*) AS num_dup_edges
WHERE num_dup_edges > 1
WITH DISTINCT node_with_dup_edges, edge_type, edge_branch, peer, is_outbound
CALL {
    // ------------
    // Get the earliest active and deleted edges for this branch
    // ------------
    WITH node_with_dup_edges, edge_type, edge_branch, peer, is_outbound
    OPTIONAL MATCH (node_with_dup_edges)-[active_edge {branch: edge_branch, status: "active"}]-(peer)
    WHERE type(active_edge) = edge_type
    AND (%(id_func_name)s(startNode(active_edge)) = %(id_func_name)s(node_with_dup_edges) OR is_outbound = FALSE)
    WITH node_with_dup_edges, edge_type, edge_branch, peer, is_outbound, active_edge
    ORDER BY active_edge.from ASC
    WITH node_with_dup_edges, edge_type, edge_branch, peer, is_outbound, head(collect(active_edge.from)) AS active_from
    OPTIONAL MATCH (node_with_dup_edges)-[deleted_edge {branch: edge_branch, status: "deleted"}]-(peer)
    WHERE %(id_func_name)s(startNode(deleted_edge)) = %(id_func_name)s(node_with_dup_edges) OR is_outbound = FALSE
    WITH node_with_dup_edges, edge_type, edge_branch, peer, is_outbound, active_from, deleted_edge
    ORDER BY deleted_edge.from DESC
    WITH node_with_dup_edges, edge_type, edge_branch, peer, is_outbound, active_from, head(collect(deleted_edge.from)) AS deleted_from
    // ------------
    // ensure one active edge with correct from and to times
    // set the others to be deleted
    // ------------
    CALL {
        WITH node_with_dup_edges, edge_type, edge_branch, peer, is_outbound, active_from, deleted_from
        OPTIONAL MATCH (node_with_dup_edges)-[active_e {branch: edge_branch, status: "active"}]-(peer)
        WHERE type(active_e) = edge_type
        AND (%(id_func_name)s(startNode(active_e)) = %(id_func_name)s(node_with_dup_edges) OR is_outbound = FALSE)
        WITH active_from, deleted_from, collect(active_e) AS active_edges
        WITH active_from, deleted_from, head(active_edges) AS edge_to_keep, tail(active_edges) AS edges_to_delete
        SET edge_to_keep.from = active_from
        SET edge_to_keep.to = deleted_from
        WITH edges_to_delete
        UNWIND edges_to_delete AS edge_to_delete
        SET edge_to_delete.to_delete = TRUE
    }
    // ------------
    // ensure one deleted edge with correct from time, if necessary
    // set the others to be deleted
    // ------------
    CALL {
        WITH node_with_dup_edges, edge_type, edge_branch, peer, is_outbound, deleted_from
        MATCH (node_with_dup_edges)-[deleted_e {branch: edge_branch, status: "deleted"}]-(peer)
        WHERE type(deleted_e) = edge_type
        AND (%(id_func_name)s(startNode(deleted_e)) = %(id_func_name)s(node_with_dup_edges) OR is_outbound = FALSE)
        WITH deleted_from, collect(deleted_e) AS deleted_edges
        WITH deleted_from, head(deleted_edges) AS edge_to_keep, tail(deleted_edges) AS edges_to_delete
        SET edge_to_keep.from = deleted_from
        WITH edges_to_delete
        UNWIND edges_to_delete AS edge_to_delete
        SET edge_to_delete.to_delete = TRUE
    }
}
        """ % {"id_func_name": db.get_id_function_name()}
        self.add_to_query(query)


class DeleteIllegalRelationships(Query):
    """
    Find all Relationship vertices with the same UUID (in a valid database, there are none)
    If any of these Relationships have an IS_RELATED edge to a deleted Node, then delete them
        this includes if an IS_RELATED edge was added on a branch after the Node was deleted on main or -global-
    If any of these Relationships are now only connected to a single Node, then delete them
    """

    name = "delete_illegal_relationships"
    type = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
// ------------
// Get the default and global branch names
// ------------
MATCH (default_b:Branch)
WHERE default_b.is_default = TRUE
WITH default_b.name AS default_branch
LIMIT 1
MATCH (global_b:Branch)
WHERE global_b.is_global = TRUE
WITH default_branch, global_b.name AS global_branch
LIMIT 1
// ------------
// Find relationships with duplicate UUIDs
// ------------
MATCH (r: Relationship)
WITH default_branch, global_branch, r.uuid AS r_uuid, count(*) AS num_dups
WHERE num_dups > 1
WITH DISTINCT default_branch, global_branch, r_uuid
// ------------
// Find any IS_RELATED edges on the duplicate Relationships that link to deleted Nodes,
//   accounting for if the edge was added on a branch after the Node was deleted on main
// ------------
CALL {
    WITH default_branch, global_branch, r_uuid
    MATCH (:Relationship {uuid: r_uuid})-[is_related:IS_RELATED]-(n:Node)
    CALL {
        WITH is_related
        MATCH (b:Branch {name: is_related.branch})
        RETURN b.branched_from AS edge_branched_from_time
    }
    // ------------
    // If this Node was deleted
    // ------------
    MATCH (n)-[is_part_of:IS_PART_OF]->(:Root)
    WHERE (is_part_of.status = "deleted" OR is_part_of.to IS NOT NULL)
    // ------------
    // before the active IS_RELATED edge's from time, then delete the edge
    // ------------
    WITH default_branch, global_branch, is_related, edge_branched_from_time, is_part_of, CASE
        WHEN is_part_of.status = "deleted" THEN is_part_of.from
        ELSE is_part_of.to
    END AS node_deleted_time
    WHERE (is_part_of.branch IN [is_related.branch, global_branch] AND is_related.from > node_deleted_time)
    OR (is_part_of.branch = default_branch AND node_deleted_time < edge_branched_from_time)
    DELETE is_related
}
MATCH (rel:Relationship {uuid: r_uuid})
CALL {
    WITH rel
    OPTIONAL MATCH (rel)-[:IS_RELATED]-(n:Node)
    WITH DISTINCT n
    RETURN count(*) AS num_peers
}
WITH rel
WHERE num_peers < 2
DETACH DELETE rel
        """
        self.add_to_query(query)


class DeleteDuplicateRelationships(Query):
    """
    There can also be leftover duplicate active Relationships that do not have the same UUID.
    They are linked to the same Nodes, have the same Relationship.name, and are on the same branch.
    In this case, we want to DETACH DELETE the later Relationship. We won't lose any information b/c the exact
    same Relationship (maybe with an earlier from time) still exists.
    """

    name = "delete_duplicate_relationships"
    type = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
MATCH (n:Node)
WITH n.uuid AS node_uuid, count(*) as num_nodes_with_uuid
WHERE num_nodes_with_uuid > 1
WITH DISTINCT node_uuid
ORDER BY node_uuid ASC
MATCH (a:Node {uuid: node_uuid})-[e1:IS_RELATED {status: "active"}]-(rel:Relationship)-[e2:IS_RELATED {branch: e1.branch, status: "active"}]-(b:Node)
WHERE a.uuid <> b.uuid
AND e1.to IS NULL
AND e2.to IS NULL
WITH a, rel.name AS rel_name, rel, b, e1.branch AS branch, CASE
    WHEN startNode(e1) = a AND startNode(e2) = rel THEN "out"
    WHEN startNode(e1) = rel AND startNode(e2) = b THEN "in"
    ELSE "bidir"
END AS direction,
CASE
    WHEN e1.from < e2.from THEN e1.from ELSE e2.from
END AS earliest_from
ORDER BY %(id_func_name)s(a), rel_name, %(id_func_name)s(b), direction, branch, earliest_from ASC
WITH a, rel_name, b, direction, branch, collect(rel) AS relationships_list
WHERE size(relationships_list) > 1
WITH a, rel_name, b, direction, branch, tail(relationships_list) AS rels_to_delete
UNWIND rels_to_delete AS rel_to_delete
DETACH DELETE rel_to_delete
        """ % {"id_func_name": db.get_id_function_name()}
        self.add_to_query(query)


class PerformHardDeletes(Query):
    name = "do_hard_deletes"
    type = QueryType.WRITE
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
CALL {
    MATCH (n)
    WHERE n.to_delete = TRUE
    DETACH DELETE n
}
CALL {
    MATCH ()-[e]-()
    WHERE e.to_delete = TRUE
    DELETE e
}
        """
        self.add_to_query(query)


class Migration029(ArbitraryMigration):
    """
    Clean up a variety of bad data created during bugged merges for node kind/inheritance updates

    1. Identify improperly duplicated nodes (ie nodes with the same UUID and the same database labels)
        a. Consolidate edges onto a single duplicated node, making sure that the edges remain active if ANY active path exists
        b. Delete the duplicated edges
        c. Delete the duplicated nodes
    2. Delete duplicated Relationships linked to the de-duplicated node
    3. Delete duplicated edges across the database

    Some of these changes must be batched because there can be a lot of them and the queries can be rather complex
    Some of these queries also require marking nodes and edges as to be deleted (using the `to_delete` property) and then
    deleting them in a separate query
    """

    name: str = "029_duplicates_cleanup"
    minimum_version: int = 28
    limit: int = 100

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        result = MigrationResult()

        return result

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        migration_result = MigrationResult()
        limit = self.limit
        offset = 0
        more_nodes_to_process = True
        try:
            while more_nodes_to_process:
                log.info(f"Running node duplicates cleanup query {limit=},{offset=}")
                node_cleanup_query = await CleanUpDuplicatedUuidVertices.init(
                    db=db,
                    vertex_label="Node",
                    limit=limit,
                    offset=offset,
                    outbound_edge_types=[
                        DatabaseEdgeType.IS_PART_OF,
                        DatabaseEdgeType.HAS_ATTRIBUTE,
                        DatabaseEdgeType.IS_RELATED,
                        DatabaseEdgeType.IS_RESERVED,
                    ],
                    inbound_edge_types=[
                        DatabaseEdgeType.IS_RELATED,
                        DatabaseEdgeType.HAS_OWNER,
                        DatabaseEdgeType.HAS_SOURCE,
                    ],
                )
                await node_cleanup_query.execute(db=db)
                has_results = False
                for result in node_cleanup_query.get_results():
                    has_results = True
                    more_nodes_to_process = result.get_as_type("more_nodes_to_process", bool)
                offset += limit
                if not has_results or not more_nodes_to_process:
                    break

            hard_delete_query = await PerformHardDeletes.init(db=db)
            await hard_delete_query.execute(db=db)

            duplicate_edge_query = await DeleteDuplicatedEdgesQuery.init(db=db)
            await duplicate_edge_query.execute(db=db)

            hard_delete_query = await PerformHardDeletes.init(db=db)
            await hard_delete_query.execute(db=db)

            illegal_relationships_cleanup_query = await DeleteIllegalRelationships.init(db=db)
            await illegal_relationships_cleanup_query.execute(db=db)

            offset = 0
            more_nodes_to_process = True
            while more_nodes_to_process:
                log.info(f"Running relationship duplicates cleanup query {limit=},{offset=}")
                relationship_cleanup_query = await CleanUpDuplicatedUuidVertices.init(
                    db=db,
                    vertex_label="Relationship",
                    limit=limit,
                    offset=offset,
                    outbound_edge_types=[
                        DatabaseEdgeType.IS_RELATED,
                        DatabaseEdgeType.IS_VISIBLE,
                        DatabaseEdgeType.IS_PROTECTED,
                        DatabaseEdgeType.HAS_OWNER,
                        DatabaseEdgeType.HAS_SOURCE,
                    ],
                    inbound_edge_types=[
                        DatabaseEdgeType.IS_RELATED,
                    ],
                )
                await relationship_cleanup_query.execute(db=db)
                has_results = False
                for result in relationship_cleanup_query.get_results():
                    has_results = True
                    more_nodes_to_process = result.get_as_type("more_nodes_to_process", bool)
                offset += limit
                if not has_results or not more_nodes_to_process:
                    break

            hard_delete_query = await PerformHardDeletes.init(db=db)
            await hard_delete_query.execute(db=db)

            duplicate_relationships_cleanup_query = await DeleteDuplicateRelationships.init(db=db)
            await duplicate_relationships_cleanup_query.execute(db=db)

        except Exception as exc:
            migration_result.errors.append(str(exc))
            return migration_result

        return migration_result
