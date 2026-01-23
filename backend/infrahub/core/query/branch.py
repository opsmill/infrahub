from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.branch.enums import BranchStatus
from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.query import Query, QueryType
from infrahub.core.query.standard_node import StandardNodeGetListQuery

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class DeleteBranchRelationshipsQuery(Query):
    name: str = "delete_branch_relationships"
    insert_return: bool = False

    type: QueryType = QueryType.WRITE

    def __init__(self, branch_name: str, **kwargs: Any) -> None:
        self.branch_name = branch_name
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
// --------------
// for every Node that only exists on this branch (it's about to be deleted),
// find any agnostic relationships or attributes connected to the Node and delete them
// --------------
OPTIONAL MATCH (:Root)<-[e:IS_PART_OF {status: "active"}]-(n:Node)
WHERE e.branch = $branch_name
// does the node only exist on this branch?
CALL (n) {
    OPTIONAL MATCH (n)-[ipo:IS_PART_OF {status: "active"}]->(:Root)
    WHERE ipo.branch <> $branch_name
    LIMIT 1
    RETURN ipo IS NOT NULL AS node_exists_on_other_branch
}
// if so, delete any linked agnostic relationships or attributes
CALL (n, node_exists_on_other_branch) {
    WITH n, node_exists_on_other_branch
    WHERE node_exists_on_other_branch = FALSE
    OPTIONAL MATCH (n)-[:IS_RELATED {branch: $global_branch_name}]-(rel:Relationship)
    DETACH DELETE rel
} IN TRANSACTIONS OF 500 ROWS
CALL (n, node_exists_on_other_branch) {
    WITH n, node_exists_on_other_branch
    WHERE node_exists_on_other_branch = FALSE
    OPTIONAL MATCH (n)-[:HAS_ATTRIBUTE {branch: $global_branch_name}]-(attr:Attribute)
    DETACH DELETE attr
} IN TRANSACTIONS OF 500 ROWS

// reduce the results to a single row
WITH 1 AS one
LIMIT 1

// --------------
// for every edge on this branch, delete it
// --------------
MATCH (s)-[r]->(d)
WHERE r.branch = $branch_name
CALL (r) {
    DELETE r
} IN TRANSACTIONS OF 500 ROWS

// --------------
// get the database IDs of every vertex linked to a deleted edge
// --------------
WITH DISTINCT elementId(s) AS s_id, elementId(d) AS d_id
WITH collect(s_id) + collect(d_id) AS vertex_ids
UNWIND vertex_ids AS vertex_id

// --------------
// delete any vertices that are now orphaned
// --------------
CALL (vertex_id) {
    MATCH (n)
    WHERE elementId(n) = vertex_id
    AND NOT exists((n)--())
    DELETE n
} IN TRANSACTIONS OF 500 ROWS
        """
        self.params["branch_name"] = self.branch_name
        self.params["global_branch_name"] = GLOBAL_BRANCH_NAME
        self.add_to_query(query)


class RebaseBranchQuery(Query):
    """Rebase a branch onto the default branch by updating edge timestamps

    For every edge on this branch
        if it has a from time before $at and no to time, update it to $at
        if it has a to time before $at, delete the edge
        if it has a to time after $at, update the from time to $at
    Then delete any orphaned vertices
    """

    name: str = "rebase_branch"
    type: QueryType = QueryType.WRITE
    insert_return: bool = False
    raise_error_if_empty: bool = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params["branch_name"] = self.branch.name
        self.params["at"] = self.at.to_string()

        query = """
// --------------
// Get all edges on this branch with their source and destination vertices
// --------------
MATCH (s)-[r]-(d)
WHERE r.branch = $branch_name
WITH DISTINCT r, s, d
WITH r, s, d,
    CASE
        // No `to` and `from` <= at: update
        WHEN r.to IS NULL AND r.from <= $at THEN TRUE
        // Has `to` and `to` < at: delete
        WHEN r.to IS NOT NULL AND r.to < $at THEN FALSE
        // Has `to` and `to` >= at: update
        ELSE TRUE
    END AS do_update

// --------------
// Process updates: set from = at for relationships we're keeping
// --------------
CALL (r, do_update) {
    WITH r, do_update
    WHERE do_update = TRUE
    SET r.from = $at
}

// --------------
// Delete the edges
// --------------
WITH r, s, d, do_update
WHERE do_update = FALSE
CALL (r, s, d) {
    DELETE r
}
// --------------
// Clean up any orpahned nodes edges
// --------------
WITH DISTINCT s, d
UNWIND [s, d] AS n
WITH DISTINCT n
CALL (n) {
    MATCH (n)
    WHERE NOT exists((n)--())
    DELETE n
}
        """
        self.add_to_query(query=query)


class BranchNodeGetListQuery(StandardNodeGetListQuery):
    def __init__(self, exclude_global: bool = False, **kwargs: Any) -> None:
        self.raw_filter = f"n.status <> '{BranchStatus.DELETING.value}'"

        if exclude_global:
            self.raw_filter += f" AND n.name <> '{GLOBAL_BRANCH_NAME}'"

        super().__init__(**kwargs)
