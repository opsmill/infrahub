from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.query import Query, QueryType
from infrahub.core.query.agnostic_retention import UNRETAINED_AGNOSTIC_FIELD_PREDICATE

if TYPE_CHECKING:
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class NodeAgnosticRetirementResult:
    """What one retirement run over a set of nodes changed."""

    edges_closed: int
    """How many global edges this run gave a `to` timestamp."""


_RETIRE_UNRETAINED_FIELDS_OF_NODES = """
// -----------------
// MATCH on the branch-agnostic edges we care about to start with.
// -----------------
MATCH (anchor_node:Node)-[anchor:HAS_ATTRIBUTE|IS_RELATED]-(field:Attribute|Relationship)
WHERE anchor_node.uuid IN $node_uuids
  AND anchor.branch = $global_branch_name
  AND anchor.status = "active"
  AND anchor.from <= $at
  AND anchor.to IS NULL
WITH collect(DISTINCT field) AS agnostic_candidates
%(unretained_predicate)s

MATCH (field)-[e]-()
WHERE e.branch = $global_branch_name
  AND e.status = "active"
  AND e.from <= $at
  AND e.to IS NULL
SET e.to = $at, e.to_user_id = $user_id
RETURN count(e) AS edges_closed
""" % {"unretained_predicate": UNRETAINED_AGNOSTIC_FIELD_PREDICATE}


class RetireNodeAgnosticFieldsQuery(Query):
    """Close the open global edges of the given nodes' branch-agnostic fields that no branch retains.

    Checks if the field is reachable from ANY branch. It is only deleted if it is completely
    unreachable.
    """

    name: str = "retire_node_agnostic_fields"
    type: QueryType = QueryType.WRITE

    insert_return: bool = False
    insert_limit: bool = False

    def __init__(self, node_uuids: list[str], at: Timestamp, **kwargs: Any) -> None:
        self.node_uuids = node_uuids
        super().__init__(at=at, **kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["global_branch_name"] = GLOBAL_BRANCH_NAME
        self.params["node_uuids"] = self.node_uuids
        self.params["at"] = self.at.to_string()
        self.params["user_id"] = self.user_id

        self.add_to_query(_RETIRE_UNRETAINED_FIELDS_OF_NODES)
        self.update_return_labels(["edges_closed"])

    def get_data(self) -> NodeAgnosticRetirementResult:
        """Return what the run closed."""
        result = self.get_result()
        if result:
            return NodeAgnosticRetirementResult(edges_closed=result.get_as_type("edges_closed", int))
        return NodeAgnosticRetirementResult(edges_closed=0)
