from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any

from infrahub.core.constants import GLOBAL_BRANCH_NAME
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


def _rollback_branches(target_branch: Branch, rollback_scope: RollbackScope) -> list[dict[str, Any]]:
    """The branches to undo, each with the time comparison that identifies this operation's writes.

    The target branch follows the scope. All changes on the branch for the scope (exact or range)
    are assumed to be part of a single group of changes.

    The global branch is always included, and always matched on the exact timestamp. Only exact
    timestamp changes are rolled back on the global branch b/c changes with later timestamps could
    be from change groups on other branches.
    """
    branches: list[dict[str, Any]] = [
        {"name": target_branch.name, "exact": rollback_scope is RollbackScope.AT_TIMESTAMP}
    ]
    if target_branch.name != GLOBAL_BRANCH_NAME:
        branches.append({"name": GLOBAL_BRANCH_NAME, "exact": True})
    return branches


def _render_restore_metadata_pipeline() -> str:
    """Restore the metadata snapshots of the vertices an edge reversal touched.

    Matches the operation's exact timestamp on every pass, independent of branch and scope.
    All ``updated_at`` properties on ``:Node``, ``:Attribute``, and ``:Relationship`` vertexes
    are assumed to be updated at the exact timestamp if changed on the default/global branches.
    The exact timestamp match also ensures that metadata is only restored one time and never
    attempts multiple restores, which would lead to NULL updated_at/by.
    """
    return """
    UNWIND [src, dst] AS endpoint
    OPTIONAL MATCH (endpoint:Attribute|Relationship)-[:HAS_ATTRIBUTE|IS_RELATED]-(owner:Node)
    WHERE owner.updated_at = $at
    UNWIND [endpoint, owner] AS restore_vertex
    WITH DISTINCT restore_vertex
    WHERE restore_vertex.updated_at = $at
    SET restore_vertex.updated_at = restore_vertex.previous_updated_at,
        restore_vertex.updated_by = restore_vertex.previous_updated_by
    SET restore_vertex.previous_updated_at = NULL, restore_vertex.previous_updated_by = NULL
    """


class RollbackReopenEdgesQuery(Query):
    """Reopen every edge that was closed in the rollback window, on every rollback branch.

    Resets `to`/`to_user_id` back to NULL, and restores the vertex metadata snapshots for each
    edge's endpoints in the same batched transaction as the edge reversal itself. Bundling the
    cleanup with the edge it belongs to keeps an interrupted run resumable: a committed batch
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
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.rollback_at = at
        self.target_branch = target_branch
        self.scope = scope

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "at": self.rollback_at.to_string(),
            "rollback_branches": _rollback_branches(target_branch=self.target_branch, rollback_scope=self.scope),
        }
        query = """
UNWIND $rollback_branches AS rollback_branch
MATCH (src)-[edge {branch: rollback_branch.name}]->(dst)
WHERE (rollback_branch.exact AND edge.to = $at)
   OR (NOT rollback_branch.exact AND edge.to >= $at)
CALL (edge, src, dst) {
    SET edge.to = NULL, edge.to_user_id = NULL
    WITH src, dst%(restore)s
} IN TRANSACTIONS OF 500 ROWS
""" % {"restore": _render_restore_metadata_pipeline()}
        self.add_to_query(query=query)


class RollbackDeleteEdgesQuery(Query):
    """Delete every edge that was created in the rollback window, on every rollback branch.

    Runs as two batched transactional blocks over the matched edges: first restore the vertex
    metadata snapshots for the edges' endpoints, then delete the edges, deleting any endpoint the
    deletions left with no remaining connections in the same batch as its edges. The
    restore-before-delete ordering is the crash-safety mechanism: every restore commits before the
    first edge deletion, so at any interruption point the not-yet-deleted edges still match a
    re-run and the already-done restores repeat as window-filtered no-ops.
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
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.rollback_at = at
        self.target_branch = target_branch
        self.scope = scope

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "at": self.rollback_at.to_string(),
            "rollback_branches": _rollback_branches(target_branch=self.target_branch, rollback_scope=self.scope),
        }
        query = """
UNWIND $rollback_branches AS rollback_branch
MATCH (src)-[edge {branch: rollback_branch.name}]->(dst)
WHERE (rollback_branch.exact AND edge.from = $at)
   OR (NOT rollback_branch.exact AND edge.from >= $at)
CALL (src, dst) {
    %(restore)s
} IN TRANSACTIONS OF 500 ROWS
CALL (edge, src, dst) {
    DELETE edge
    WITH src, dst
    UNWIND [src, dst] AS endpoint
    WITH DISTINCT endpoint
    WHERE NOT exists((endpoint)--())
    DELETE endpoint
} IN TRANSACTIONS OF 500 ROWS
""" % {"restore": _render_restore_metadata_pipeline()}
        self.add_to_query(query=query)
