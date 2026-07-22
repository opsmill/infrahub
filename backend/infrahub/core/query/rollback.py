from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any

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

    @property
    def operator(self) -> str:
        return "=" if self is RollbackScope.AT_TIMESTAMP else ">="


class RollbackReopenEdgesQuery(Query):
    """Reopen every edge that was closed in the rollback window.

    Resets `to`/`to_user_id` back to NULL and returns the element ids of the vertices on either
    end of every reopened edge, so the caller can restore vertex metadata afterwards.

    All edge types are covered in a single label-less pass.
    """

    name = "rollback_reopen_edges"
    type = QueryType.WRITE
    raise_error_if_empty = False

    def __init__(
        self,
        at: Timestamp,
        target_branch: Branch,
        scope: RollbackScope,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.rollback_at = at
        self.target_branch = target_branch
        self.scope = scope

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "at": self.rollback_at.to_string(),
            "target_branch": self.target_branch.name,
        }
        query = """
MATCH (src)-[edge {branch: $target_branch}]->(dst)
WHERE edge.to %(op)s $at
CALL (edge) {
    SET edge.to = NULL, edge.to_user_id = NULL
} IN TRANSACTIONS OF 500 ROWS
UNWIND [elementId(src), elementId(dst)] AS vertex_id
WITH DISTINCT vertex_id
""" % {"op": self.scope.operator}
        self.add_to_query(query=query)
        self.return_labels = ["vertex_id"]

    def get_touched_vertex_ids(self) -> list[str]:
        return [result.get_as_type("vertex_id", str) for result in self.get_results()]


class RollbackDeleteEdgesQuery(Query):
    """Delete every edge that was created in the rollback window.

    Returns the element ids of the vertices on either end of every deleted edge: they are both
    the orphan candidates for the vertex cleanup and the targets of the vertex metadata restore.

    All edge types are covered in a single label-less pass.
    """

    name = "rollback_delete_edges"
    type = QueryType.WRITE
    raise_error_if_empty = False

    def __init__(
        self,
        at: Timestamp,
        target_branch: Branch,
        scope: RollbackScope,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.rollback_at = at
        self.target_branch = target_branch
        self.scope = scope

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "at": self.rollback_at.to_string(),
            "target_branch": self.target_branch.name,
        }
        query = """
MATCH (src)-[edge {branch: $target_branch}]->(dst)
WHERE edge.from %(op)s $at
CALL (edge) {
    DELETE edge
} IN TRANSACTIONS OF 500 ROWS
UNWIND [elementId(src), elementId(dst)] AS vertex_id
WITH DISTINCT vertex_id
""" % {"op": self.scope.operator}
        self.add_to_query(query=query)
        self.return_labels = ["vertex_id"]

    def get_touched_vertex_ids(self) -> list[str]:
        return [result.get_as_type("vertex_id", str) for result in self.get_results()]


class RollbackDeleteOrphanedVerticesQuery(Query):
    """Delete the given vertices if the edge deletions left them with no remaining connections.

    Scoping the check to the given vertex ids is a safety boundary, not just an optimization:
    a whole-graph orphan sweep would also delete vertices orphaned by something other than the
    rollback — pre-existing debris, or a vertex a concurrent writer has created but not yet
    connected.
    """

    name = "rollback_delete_orphaned_vertices"
    type = QueryType.WRITE
    insert_return = False
    raise_error_if_empty = False

    def __init__(self, vertex_ids: list[str], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.vertex_ids = vertex_ids

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {"vertex_ids": self.vertex_ids}
        query = """
UNWIND $vertex_ids AS vertex_id
MATCH (orphan)
WHERE elementId(orphan) = vertex_id
AND NOT exists((orphan)--())
CALL (orphan) {
    DELETE orphan
} IN TRANSACTIONS OF 500 ROWS
"""
        self.add_to_query(query=query)


class RollbackRestoreMetadataQuery(Query):
    """Restore the updated_at/updated_by snapshots on vertices bumped in the rollback window.

    Covers the given vertices plus the Node vertices owning any of them that is an
    Attribute/Relationship vertex (a value change reverts edges on the field vertex only, while
    the merge metadata bump also stamps the owning Node). Only vertices whose `updated_at` falls
    inside the rollback window are restored, so vertices the window never bumped keep their
    metadata.

    Counts on `previous_updated_at`/`previous_updated_by` being set on the vertex. Does not
    recalculate updated_at/updated_by metadata.
    """

    name = "rollback_restore_metadata"
    type = QueryType.WRITE
    insert_return = False
    raise_error_if_empty = False

    def __init__(
        self,
        vertex_ids: list[str],
        at: Timestamp,
        scope: RollbackScope,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.vertex_ids = vertex_ids
        self.rollback_at = at
        self.scope = scope

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "at": self.rollback_at.to_string(),
            "vertex_ids": self.vertex_ids,
        }
        query = """
UNWIND $vertex_ids AS vertex_id
MATCH (touched)
WHERE elementId(touched) = vertex_id
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
} IN TRANSACTIONS OF 500 ROWS
""" % {"op": self.scope.operator}
        self.add_to_query(query=query)
