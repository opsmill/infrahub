from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


class RollbackQuery(Query):
    """Rollback all database changes made at a specific timestamp on a branch.

    This query reverses database changes by:
    1. (Optional) Restoring `previous_updated_at`/`previous_updated_by` snapshots on the given
       set of node UUIDs and their connected Attribute/Relationship vertices.
    2. Resetting `to` times (and `to_user_id`) back to NULL for edges that were closed
       at the given timestamp.
    3. Deleting edges that were created at the given timestamp.
    4. Deleting any vertices that become orphaned after the edge deletions.

    All write subqueries use `CALL { ... } IN TRANSACTIONS` so the query stays a non-writer
    at the outer level. This both batches the writes and keeps each `CALL IN TRANSACTIONS`
    legal regardless of how many earlier subqueries also wrote.
    """

    name = "rollback"
    type = QueryType.WRITE
    insert_return = False

    def __init__(
        self,
        at: Timestamp,
        target_branch: Branch,
        node_uuids: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.rollback_at = at
        self.target_branch = target_branch
        self.node_uuids = node_uuids or []

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "at": self.rollback_at.to_string(),
            "target_branch": self.target_branch.name,
            "node_uuids": self.node_uuids,
        }

        query = """
// ---------------------------
// Restore previous_updated_at/by on affected Node vertices
// ---------------------------
OPTIONAL MATCH (n:Node)
WHERE n.uuid IN $node_uuids
AND n.previous_updated_at IS NOT NULL
CALL (n) {
    SET n.updated_at = n.previous_updated_at, n.updated_by = n.previous_updated_by
    SET n.previous_updated_at = NULL, n.previous_updated_by = NULL
} IN TRANSACTIONS OF 500 ROWS
// ---------------------------
// Restore previous_updated_at/by on connected Attribute/Relationship vertices
// ---------------------------
OPTIONAL MATCH (n)-[:HAS_ATTRIBUTE|IS_RELATED {branch: $target_branch}]-(attr_rel:Attribute|Relationship)
WHERE attr_rel.previous_updated_at IS NOT NULL
WITH DISTINCT attr_rel
CALL (attr_rel) {
    SET attr_rel.updated_at = attr_rel.previous_updated_at, attr_rel.updated_by = attr_rel.previous_updated_by
    SET attr_rel.previous_updated_at = NULL, attr_rel.previous_updated_by = NULL
} IN TRANSACTIONS OF 500 ROWS

// ---------------------------
// separate query phases, reduce to single row
// ---------------------------
WITH 1 AS one
LIMIT 1

// ---------------------------
// Reset 'to' times: restore relationships that were closed at this timestamp
// ---------------------------
OPTIONAL MATCH ()-[r_to {to: $at, branch: $target_branch}]->()
CALL (r_to) {
    SET r_to.to = NULL, r_to.to_user_id = NULL
} IN TRANSACTIONS OF 500 ROWS

// ---------------------------
// separate query phases, reduce to single row
// ---------------------------
WITH 1 AS one
LIMIT 1

// ---------------------------
// Delete 'from' times: remove relationships that were created at this timestamp
// and collect the vertex IDs of connected nodes
// ---------------------------
MATCH (s)-[r {from: $at, branch: $target_branch}]->(d)
CALL (r) {
    DELETE r
} IN TRANSACTIONS OF 500 ROWS

// ---------------------------
// Collect the database IDs of all vertices that were connected to deleted edges
// ---------------------------
WITH DISTINCT elementId(s) AS s_id, elementId(d) AS d_id
WITH collect(s_id) + collect(d_id) AS vertex_ids

// ---------------------------
// Delete any vertices that are now orphaned (have no remaining connections)
// ---------------------------
MATCH (n)
WHERE elementId(n) IN vertex_ids
AND NOT exists((n)--())
CALL (n) {
    DELETE n
} IN TRANSACTIONS OF 500 ROWS
"""
        self.add_to_query(query=query)
