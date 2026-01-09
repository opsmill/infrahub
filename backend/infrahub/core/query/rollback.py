from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.timestamp import Timestamp


class RollbackQuery(Query):
    """Rollback all database changes made at a specific timestamp on a branch.

    This query reverses database changes by:
    1. Resetting `to` times back to NULL for relationships that were closed at the given timestamp
    2. Deleting relationships that were created at the given timestamp
    3. Deleting any vertices that become orphaned after the edge deletions
    """

    name = "rollback"
    type = QueryType.WRITE
    insert_return = False

    def __init__(self, at: Timestamp, target_branch: Branch, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.rollback_at = at
        self.target_branch = target_branch
        self.params = {
            "at": self.rollback_at.to_string(),
            "target_branch": self.target_branch.name,
        }
        query = """
        // ---------------------------
        // Reset 'to' times: restore relationships that were closed at this timestamp
        // ---------------------------
        CALL () {
            OPTIONAL MATCH ()-[r_to {to: $at, branch: $target_branch}]-()
            SET r_to.to = NULL
        } IN TRANSACTIONS

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
