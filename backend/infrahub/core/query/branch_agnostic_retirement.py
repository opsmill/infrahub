from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.query import Query, QueryType
from infrahub.core.query.agnostic_retention import UNRETAINED_AGNOSTIC_FIELD_PREDICATE

if TYPE_CHECKING:
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


_RETIRE_UNRETAINED_FIELDS_OF_BRANCH = """
// -----------------
// Optional in case branch delete partially succeeded and is running again
// -----------------
OPTIONAL MATCH (deleted_branch:Branch {name: $branch_name})
WITH deleted_branch.origin_branch AS origin_name, deleted_branch.branched_from AS fork_at
// -----------------
// Every active HAS_ATTRIBUTE/IS_RELATED edge on the global branch...
// -----------------
MATCH (reachable_node:Node)-[anchor:HAS_ATTRIBUTE|IS_RELATED]-(field:Attribute|Relationship)
WHERE anchor.branch = $global_branch_name
AND anchor.status = "active"
AND anchor.from <= $at
AND anchor.to IS NULL
AND EXISTS {
    // -----------------
    // ... that is either created on this branch ...
    // -----------------
    MATCH (reachable_node)-[existence:IS_PART_OF]->(:Root)
    WHERE (existence.branch = $branch_name
            AND existence.status = "active"
            AND existence.to IS NULL)
        // -----------------
        // ... or has been deleted on the default branch
        // -----------------
        OR (existence.branch = origin_name
            AND existence.status = "active"
            AND existence.from <= fork_at
            AND existence.to > fork_at)
  }
WITH collect(DISTINCT field) AS agnostic_candidates
%(unretained_predicate)s

CALL (field) {
    MATCH (field)-[edge_to_close]-()
    WHERE edge_to_close.branch = $global_branch_name
      AND edge_to_close.status = "active"
      AND edge_to_close.from <= $at
      AND edge_to_close.to IS NULL
    SET edge_to_close.to = $at, edge_to_close.to_user_id = $user_id
    RETURN count(edge_to_close) AS batch_closed_edges
} IN TRANSACTIONS OF $batch_size ROWS
RETURN sum(batch_closed_edges) AS edges_closed
"""


class RetireBranchAgnosticFieldsQuery(Query):
    """Close the open global edges of the branch-agnostic fields only the deleted branch still retained.

    Retention is judged across every remaining branch, and a field kept live by any of them is left open.
    Must run while the branch's IS_PART_OF edges still exist, because the candidate bound reads them.

    The writes are batched, so this query cannot run inside an explicit transaction. A failure part
    way through leaves the earlier batches closed, which a re-run completes: retention does not come
    back once lost, and a closed edge is no longer a candidate.
    """

    name: str = "retire_branch_agnostic_fields"
    type: QueryType = QueryType.WRITE

    insert_return: bool = False
    insert_limit: bool = False

    def __init__(self, branch_name: str, at: Timestamp, batch_size: int, **kwargs: Any) -> None:
        self.branch_name = branch_name
        self.batch_size = batch_size
        super().__init__(at=at, **kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["global_branch_name"] = GLOBAL_BRANCH_NAME
        self.params["branch_name"] = self.branch_name
        self.params["at"] = self.at.to_string()
        self.params["batch_size"] = self.batch_size
        self.params["user_id"] = self.user_id

        self.add_to_query(
            _RETIRE_UNRETAINED_FIELDS_OF_BRANCH % {"unretained_predicate": UNRETAINED_AGNOSTIC_FIELD_PREDICATE}
        )
        self.update_return_labels(["edges_closed"])

    def closed_edge_count(self) -> int:
        """How many global edges this run stamped shut."""
        result = self.get_result()
        if result is None:
            return 0
        return result.get_as_type("edges_closed", int)
