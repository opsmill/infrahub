from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any

from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


class RollbackScope(Enum):
    """Which writes on the target branch a rollback reverses.

    AT_TIMESTAMP reverses only writes stamped exactly at the rollback timestamp. It is for callers
    that run every operation to revert at a single unified timestamp while other writers may still
    be active on the branch — a range would revert those unrelated writes too.

    SINCE_TIMESTAMP reverses every write stamped at or after the rollback timestamp. It is only
    safe when the caller owns all writes on the target branch from that point on (the merge
    write-block guarantees this for the merge window).
    """

    AT_TIMESTAMP = "at_timestamp"
    SINCE_TIMESTAMP = "since_timestamp"


class RollbackQuery(Query):
    """Rollback database changes made on a branch at (or since) a timestamp.

    This query reverses database changes by:
    1. Resetting `to` times (and `to_user_id`) back to NULL for edges that were closed
       in the rollback window.
    2. Deleting edges that were created in the rollback window.
    3. Deleting any vertices that become orphaned after the edge deletions.
    4. (Optional) Restoring the `previous_updated_at`/`previous_updated_by` snapshots on the
       vertices the rolled-back writes had bumped: the vertices connected to a reverted edge,
       plus the Node vertices owning any such Attribute/Relationship vertex (a value change
       reverts edges on the field vertex only, while the merge metadata bump also stamps the
       owning Node). Only vertices whose `updated_at` falls inside the rollback window are
       restored, so vertices the window never bumped keep their metadata. Restoring is only
       allowed when the target branch is the default or global branch — vertex metadata
       properties are maintained solely for those branches, so there is nothing to restore
       anywhere else.

    Reverting updated_at/by metadata counts on the previous_updated_at/by being set on the
    vertex. Does not recalculate updated_at/by metadata.

    Edge phases are written as one subquery per edge type because relationship indexes are
    per-type; a label-less relationship match cannot use them.

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
        scope: RollbackScope,
        restore_metadata: bool,
        **kwargs: Any,
    ) -> None:
        if restore_metadata and not (target_branch.is_default or target_branch.is_global):
            raise ValueError("restore_metadata is only allowed when the target branch is the default or global branch")
        super().__init__(**kwargs)
        self.rollback_at = at
        self.target_branch = target_branch
        self.scope = scope
        self.restore_metadata = restore_metadata

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "at": self.rollback_at.to_string(),
            "target_branch": self.target_branch.name,
        }

        op = "=" if self.scope is RollbackScope.AT_TIMESTAMP else ">="

        phases: list[str] = ["WITH [] AS vertex_ids"]

        reopen_template = """
// ---------------------------
// Reset 'to' times: restore %(edge_type)s edges that were closed in the rollback window
// ---------------------------
OPTIONAL MATCH (reopen_src)-[reopen_edge:%(edge_type)s {branch: $target_branch}]->(reopen_dst)
WHERE reopen_edge.to %(op)s $at
CALL (reopen_edge) {
    SET reopen_edge.to = NULL, reopen_edge.to_user_id = NULL
} IN TRANSACTIONS OF 500 ROWS
WITH vertex_ids, collect(DISTINCT elementId(reopen_src)) + collect(DISTINCT elementId(reopen_dst)) AS touched_ids
WITH vertex_ids + touched_ids AS vertex_ids"""
        phases.extend(reopen_template % {"edge_type": edge_type.value, "op": op} for edge_type in DatabaseEdgeType)

        delete_template = """
// ---------------------------
// Delete 'from' times: remove %(edge_type)s edges that were created in the rollback window
// ---------------------------
OPTIONAL MATCH (delete_src)-[delete_edge:%(edge_type)s {branch: $target_branch}]->(delete_dst)
WHERE delete_edge.from %(op)s $at
CALL (delete_edge) {
    DELETE delete_edge
} IN TRANSACTIONS OF 500 ROWS
WITH vertex_ids, collect(DISTINCT elementId(delete_src)) + collect(DISTINCT elementId(delete_dst)) AS touched_ids
WITH vertex_ids + touched_ids AS vertex_ids"""
        phases.extend(delete_template % {"edge_type": edge_type.value, "op": op} for edge_type in DatabaseEdgeType)

        phases.append(
            """
// ---------------------------
// Deduplicate the collected vertex ids (the NULL padding keeps a row alive when nothing matched;
// collect() drops it again)
// ---------------------------
UNWIND vertex_ids + [NULL] AS vertex_id
WITH collect(DISTINCT vertex_id) AS vertex_ids

// ---------------------------
// Delete any vertices that are now orphaned (have no remaining connections)
// ---------------------------
OPTIONAL MATCH (orphan)
WHERE elementId(orphan) IN vertex_ids
AND NOT exists((orphan)--())
CALL (orphan) {
    DELETE orphan
} IN TRANSACTIONS OF 500 ROWS"""
        )

        if self.restore_metadata:
            metadata_template = """
// ---------------------------
// Restore the updated_at/by snapshots on the vertices the rolled-back writes had bumped
// ---------------------------
WITH DISTINCT vertex_ids
OPTIONAL MATCH (touched)
WHERE elementId(touched) IN vertex_ids
WITH DISTINCT touched
OPTIONAL MATCH (touched:Attribute|Relationship)-[:HAS_ATTRIBUTE|IS_RELATED]-(owner:Node)
WHERE touched.updated_at %(op)s $at
OR owner.updated_at %(op)s $at
WITH collect(DISTINCT touched) + collect(DISTINCT owner) AS restore_candidates
UNWIND restore_candidates AS restore_vertex
WITH DISTINCT restore_vertex
WHERE restore_vertex.updated_at %(op)s $at
CALL (restore_vertex) {
    SET restore_vertex.updated_at = restore_vertex.previous_updated_at,
        restore_vertex.updated_by = restore_vertex.previous_updated_by
    SET restore_vertex.previous_updated_at = NULL, restore_vertex.previous_updated_by = NULL
} IN TRANSACTIONS OF 500 ROWS"""
            phases.append(metadata_template % {"op": op})

        self.add_to_query(query="\n".join(phases))
