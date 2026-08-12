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


def _scope_to_operator(rollback_scope: RollbackScope) -> str:
    return "=" if rollback_scope is RollbackScope.AT_TIMESTAMP else ">="


def _render_restore_metadata_pipeline(rollback_scope: RollbackScope) -> str:
    operator = _scope_to_operator(rollback_scope)
    return """
    UNWIND [src, dst] AS endpoint
    OPTIONAL MATCH (endpoint:Attribute|Relationship)-[:HAS_ATTRIBUTE|IS_RELATED]-(owner:Node)
    WHERE owner.updated_at %(op)s $at
    UNWIND [endpoint, owner] AS restore_vertex
    WITH restore_vertex
    WHERE restore_vertex.updated_at %(op)s $at
    SET restore_vertex.updated_at = restore_vertex.previous_updated_at,
        restore_vertex.updated_by = restore_vertex.previous_updated_by
    SET restore_vertex.previous_updated_at = NULL, restore_vertex.previous_updated_by = NULL
    """ % {"op": operator}


class RollbackReopenEdgesQuery(Query):
    """Reopen every edge that was closed in the rollback window.

    Resets `to`/`to_user_id` back to NULL, and (optionally) restores the vertex metadata snapshots
    for each edge's endpoints in the same batched transaction as the edge reversal itself. Bundling
    the cleanup with the edge it belongs to keeps an interrupted run resumable: a committed batch
    is fully finished, and the edges of an uncommitted batch still match a re-run.
    """

    name = "rollback_reopen_edges"
    type = QueryType.WRITE
    insert_return = False
    raise_error_if_empty = False

    def __init__(
        self,
        at: Timestamp,
        target_branch: Branch,
        scope: RollbackScope,
        restore_metadata: bool,
        **kwargs: Any,
    ) -> None:
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
        restore = ""
        if self.restore_metadata:
            restore = "\n    WITH src, dst" + _render_restore_metadata_pipeline(rollback_scope=self.scope)
        query = """
MATCH (src)-[edge {branch: $target_branch}]->(dst)
WHERE edge.to %(op)s $at
CALL (edge, src, dst) {
    SET edge.to = NULL, edge.to_user_id = NULL%(restore)s
} IN TRANSACTIONS OF 500 ROWS
""" % {"op": _scope_to_operator(self.scope), "restore": restore}
        self.add_to_query(query=query)


class RollbackDeleteEdgesQuery(Query):
    """Delete every edge that was created in the rollback window.

    Runs as two batched transactional blocks over the matched edges: first restore the vertex
    metadata snapshots for the edges' endpoints (skipped when ``restore_metadata`` is off), then
    delete the edges, deleting any endpoint the deletions left with no remaining connections in
    the same batch as its edges. The restore-before-delete ordering is the crash-safety mechanism:
    every restore commits before the first edge deletion, so at any interruption point the
    not-yet-deleted edges still match a re-run and the already-done restores repeat as
    window-filtered no-ops.
    """

    name = "rollback_delete_edges"
    type = QueryType.WRITE
    insert_return = False
    raise_error_if_empty = False

    def __init__(
        self,
        at: Timestamp,
        target_branch: Branch,
        scope: RollbackScope,
        restore_metadata: bool,
        **kwargs: Any,
    ) -> None:
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
        restore_block = ""
        if self.restore_metadata:
            restore_block = """
CALL (src, dst) {
    %(pipeline)s
} IN TRANSACTIONS OF 500 ROWS
""" % {"pipeline": _render_restore_metadata_pipeline(rollback_scope=self.scope)}
        query = """
MATCH (src)-[edge {branch: $target_branch}]->(dst)
WHERE edge.from %(op)s $at
%(restore_block)s
CALL (edge, src, dst) {
    DELETE edge
    WITH src, dst
    UNWIND [src, dst] AS endpoint
    WITH DISTINCT endpoint
    WHERE NOT exists((endpoint)--())
    DELETE endpoint
} IN TRANSACTIONS OF 500 ROWS
""" % {"op": _scope_to_operator(rollback_scope=self.scope), "restore_block": restore_block}
        self.add_to_query(query=query)
