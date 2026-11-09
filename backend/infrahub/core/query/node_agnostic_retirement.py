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
    """Global edges given a `to` timestamp. Zero means every field is still retained somewhere."""


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


_NODES_DELETED_ON_BRANCH = """
MATCH (node:Node)-[deletion:IS_PART_OF]->(:Root)
WHERE deletion.branch = $branch_name
  AND deletion.status = "deleted"
  AND deletion.from >= $from_time
  AND deletion.from <= $to_time
// -----------------
// One row holding every uuid, so the existence edges are scanned once rather than once per page.
// -----------------
RETURN collect(DISTINCT node.uuid) AS node_uuids
"""


class NodesDeletedOnBranchQuery(Query):
    """Return the uuids of the nodes deleted on a branch between two timestamps, both included.

    A kind or inheritance change deletes the superseded vertex of a node that stays live under the same
    uuid, so a returned uuid is a node whose retention needs re-evaluating, not proof that it is gone.
    """

    name: str = "nodes_deleted_on_branch"
    type: QueryType = QueryType.READ

    insert_return: bool = False

    def __init__(self, branch_name: str, from_time: Timestamp, to_time: Timestamp, **kwargs: Any) -> None:
        self.branch_name = branch_name
        self.from_time = from_time
        self.to_time = to_time
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["branch_name"] = self.branch_name
        self.params["from_time"] = self.from_time.to_string()
        self.params["to_time"] = self.to_time.to_string()

        self.add_to_query(_NODES_DELETED_ON_BRANCH)
        self.return_labels = ["node_uuids"]

    def get_node_uuids(self) -> list[str]:
        result = self.get_result()
        if result is None:
            return []
        return result.get_as_list_of_type("node_uuids", str)
