from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.query import Query, QueryType
from infrahub.core.query.agnostic_retention import UNRETAINED_AGNOSTIC_FIELD_PREDICATE

if TYPE_CHECKING:
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


_UNRETAINED_AGNOSTIC_FIELDS_WITH_STAMP = """
// -----------------
// The anchor takes every active global owning edge, open or already closed, so a vertex left
// half-closed by an earlier version -- owning edge closed with property edges still open, or the
// reverse -- is reachable.
//
// Filter to any active :Attribute/:Relationship on the global branch that has at least one
// active edge on the global branch AND one of the following:
// - is only linked to deleted :Node vertices
// - is linked to at least 1 closed/deleted HAS_ATTRIBUTE/IS_RELATED edge
// - is a :Relationship AND is linked to fewer than 2 peers
// This is a quick preliminary filter to reduce the number of rows cheaply
// -----------------
MATCH (:Node)-[anchor:HAS_ATTRIBUTE|IS_RELATED]-(field:Attribute|Relationship)
WHERE anchor.branch = $global_branch_name
  AND anchor.status = "active"
  AND EXISTS {
      MATCH (field)-[open_global_edge]-()
      WHERE open_global_edge.branch = $global_branch_name
        AND open_global_edge.status = "active"
        AND open_global_edge.to IS NULL
  }
  AND (
      EXISTS {
          MATCH (linked:Node)-[:HAS_ATTRIBUTE|IS_RELATED]-(field)
          WHERE NOT EXISTS {
              MATCH (linked)-[linked_existence:IS_PART_OF]->(:Root)
              WHERE linked_existence.status = "active"
                AND linked_existence.to IS NULL
          }
      }
      OR EXISTS {
          MATCH (:Node)-[owning:HAS_ATTRIBUTE|IS_RELATED]-(field)
          WHERE owning.branch = $global_branch_name
            AND (owning.to IS NOT NULL OR owning.status <> "active")
      }
      OR (
          field:Relationship
          AND COUNT { MATCH (peer:Node)-[:IS_RELATED]-(field) RETURN DISTINCT peer } < 2
      )
  )
WITH collect(DISTINCT field) AS agnostic_candidates
%(unretained_predicate)s

// -----------------
// Find when the parent :Node was deleted, if at all
// -----------------
OPTIONAL CALL (field) {
    MATCH (owner:Node)-[:HAS_ATTRIBUTE|IS_RELATED]-(field)
    MATCH (owner)-[existence:IS_PART_OF]->(:Root)
    RETURN CASE
        WHEN existence.status = "deleted" THEN existence.from
        ELSE existence.to
    END AS owner_gone_at
    ORDER BY existence.from DESC, existence.status ASC
    LIMIT 1
}
CALL (field) {
    // -----------------
    // The fallback covers a field whose owner is still live: the latest close among its owning
    // edges is when the field itself stopped being reachable.
    // -----------------
    MATCH ()-[owning:HAS_ATTRIBUTE|IS_RELATED]-(field)
    WHERE owning.to IS NOT NULL
    RETURN max(owning.to) AS owning_closed_at
}
// -----------------
// The later of the two candidates, never the first non-null: a stale same-uuid owner copy left by a
// kind change would otherwise back-date the stamp past the moment the field stopped being reachable.
// -----------------
WITH field, CASE
    WHEN owner_gone_at > owning_closed_at OR owning_closed_at IS NULL THEN owner_gone_at
    ELSE owning_closed_at
END AS derived_at
WITH field, coalesce(derived_at, $at) AS retired_at
""" % {"unretained_predicate": UNRETAINED_AGNOSTIC_FIELD_PREDICATE}


_CLOSE_UNRETAINED_AGNOSTIC_FIELDS = (
    _UNRETAINED_AGNOSTIC_FIELDS_WITH_STAMP
    + """
CALL (field, retired_at) {
    MATCH (field)-[edge_to_close]-()
    WHERE edge_to_close.branch = $global_branch_name
      AND edge_to_close.status = "active"
      AND edge_to_close.to IS NULL
    // An edge opened after the derived stamp would otherwise be given an inverted interval.
    SET edge_to_close.to = CASE
        WHEN edge_to_close.from > retired_at THEN edge_to_close.from
        ELSE retired_at
    END,
    edge_to_close.to_user_id = $user_id
    RETURN count(edge_to_close) AS batch_closed_edges
} IN TRANSACTIONS OF $batch_size ROWS
RETURN sum(batch_closed_edges) AS edges_closed
"""
)


_DELETE_DETACHED_AGNOSTIC_FIELDS = """
MATCH (field:Attribute|Relationship)
WHERE NOT EXISTS { MATCH (:Node)-[:HAS_ATTRIBUTE|IS_RELATED]-(field) }
CALL (field) {
    // Nothing can reach, diff, or time-travel to such a vertex, so a time-close would leave
    // garbage no later pass could ever remove. Value vertices are shared and stay untouched.
    DETACH DELETE field
} IN TRANSACTIONS OF $batch_size ROWS
"""


class CloseUnretainedAgnosticFieldsQuery(Query):
    """Close every open global edge of the branch-agnostic fields that no branch retains.

    Unbounded: every branch-agnostic field in the graph is a candidate, which is what clears a
    backlog no runtime path can reach. Each candidate is stamped with the time it stopped being
    reachable rather than with the run time, and one that yields no such time is left alone.

    The writes are batched, so this query cannot run inside an explicit transaction. A failure part
    way through leaves the earlier batches closed, which a re-run completes: retention does not come
    back once lost, and a closed edge is no longer a candidate.
    """

    name: str = "close_unretained_agnostic_fields"
    type: QueryType = QueryType.WRITE

    insert_return: bool = False
    insert_limit: bool = False

    def __init__(self, at: Timestamp, batch_size: int, **kwargs: Any) -> None:
        self.batch_size = batch_size
        super().__init__(at=at, **kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["global_branch_name"] = GLOBAL_BRANCH_NAME
        self.params["at"] = self.at.to_string()
        self.params["batch_size"] = self.batch_size
        self.params["user_id"] = self.user_id

        self.add_to_query(_CLOSE_UNRETAINED_AGNOSTIC_FIELDS)
        self.update_return_labels(["edges_closed"])

    def closed_edge_count(self) -> int:
        """How many global edges this run stamped shut. Zero means nothing was left to release."""
        result = self.get_result()
        if result is None:
            return 0
        return result.get_as_type("edges_closed", int)


class DeleteDetachedAgnosticFieldsQuery(Query):
    """Hard-delete the `Attribute` and `Relationship` vertices no node vertex points at any more.

    What is matched is the absence of the node vertex itself, never the absence of an existence edge:
    a node vertex that is still there but reads as deleted on every branch goes on owning its fields,
    and those are time-closed rather than removed. Branch deletions predating the agnostic-peer
    cleanup removed the node vertices outright and left these ones pointing at nothing. The deletion
    is irreversible and has nothing to roll back to: with no node vertex left there is no object the
    value ever belonged to.
    """

    name: str = "delete_detached_agnostic_fields"
    type: QueryType = QueryType.WRITE

    insert_return: bool = False
    insert_limit: bool = False

    def __init__(self, batch_size: int, **kwargs: Any) -> None:
        self.batch_size = batch_size
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["batch_size"] = self.batch_size
        self.add_to_query(_DELETE_DETACHED_AGNOSTIC_FIELDS)

    def removed_vertex_count(self) -> int:
        """How many field vertices this run removed."""
        return sum(stat.nodes_deleted or 0 for stat in self.stats.stats)
