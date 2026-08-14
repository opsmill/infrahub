from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.branch.enums import TERMINAL_BRANCH_STATUSES, BranchStatus
from infrahub.core.branch.filters import BranchListFilters
from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.query import Query, QueryType
from infrahub.core.query.standard_node import StandardNodeGetListQuery
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.core.constants.database import DatabaseEdgeType
    from infrahub.database import InfrahubDatabase


class DeleteBranchAgnosticRelationshipsQuery(Query):
    """Delete the agnostic Relationship vertices attached to Nodes that only exist on this branch.

    Must run before any IS_PART_OF edge of the branch is deleted: the branch-only determination
    reads those edges, so once they are gone the affected Nodes can no longer be found and their
    agnostic peers leak.
    """

    name: str = "delete_branch_agnostic_relationships"
    insert_return: bool = False
    insert_limit: bool = False

    type: QueryType = QueryType.WRITE

    def __init__(self, branch_name: str, batch_size: int, **kwargs: Any) -> None:
        self.branch_name = branch_name
        self.batch_size = batch_size
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
MATCH (:Root)<-[e:IS_PART_OF {status: "active"}]-(n:Node)
WHERE e.branch = $branch_name
AND NOT EXISTS {
    MATCH (n)-[ipo:IS_PART_OF {status: "active"}]->(:Root)
    WHERE ipo.branch <> $branch_name
}
CALL (n) {
    MATCH (n)-[:IS_RELATED {branch: $global_branch_name}]-(rel:Relationship)
    DETACH DELETE rel
} IN TRANSACTIONS OF %(batch_size)s ROWS
        """ % {"batch_size": self.batch_size}
        self.params["branch_name"] = self.branch_name
        self.params["global_branch_name"] = GLOBAL_BRANCH_NAME
        self.add_to_query(query)


class DeleteBranchAgnosticAttributesQuery(Query):
    """Delete the agnostic Attribute vertices attached to Nodes that only exist on this branch.

    Carries the same ordering requirement as the agnostic Relationship query.
    """

    name: str = "delete_branch_agnostic_attributes"
    insert_return: bool = False
    insert_limit: bool = False

    type: QueryType = QueryType.WRITE

    def __init__(self, branch_name: str, batch_size: int, **kwargs: Any) -> None:
        self.branch_name = branch_name
        self.batch_size = batch_size
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
MATCH (:Root)<-[e:IS_PART_OF {status: "active"}]-(n:Node)
WHERE e.branch = $branch_name
AND NOT EXISTS {
    MATCH (n)-[ipo:IS_PART_OF {status: "active"}]->(:Root)
    WHERE ipo.branch <> $branch_name
}
CALL (n) {
    MATCH (n)-[:HAS_ATTRIBUTE {branch: $global_branch_name}]-(attr:Attribute)
    DETACH DELETE attr
} IN TRANSACTIONS OF %(batch_size)s ROWS
        """ % {"batch_size": self.batch_size}
        self.params["branch_name"] = self.branch_name
        self.params["global_branch_name"] = GLOBAL_BRANCH_NAME
        self.add_to_query(query)


class DeleteBranchEdgesQuery(Query):
    """Delete one batch of edges of a single type belonging to a branch, plus any vertex left bare.

    Every edge on the branch is removed by this query's DELETE, and both endpoints of each one are
    then re-examined, so a vertex is examined once per edge it had. The batch that removes its last
    edge is therefore the one that sees it at degree zero and deletes it. Nothing can be stranded,
    because no edge is ever removed by any other means -- which is why the vertices need no separate
    sweep afterwards, and why the vertex delete must not be a DETACH DELETE. A DETACH DELETE would
    take out the branch edges the vertex still had, and those edges would then never reach a batch
    of their own, leaving the vertices on their far side unexamined and orphaned.

    The DISTINCT is what makes this sound: it forces the whole batch's edge deletes to complete
    before the first vertex is examined, so degree zero means degree zero.

    Naming the edge type is what lets the `branch` range index be used for the match; the type
    cannot be a query parameter, so it is interpolated from the closed DatabaseEdgeType enum.

    Run repeatedly until it stops deleting edges.
    """

    name: str = "delete_branch_edges"
    insert_return: bool = False
    insert_limit: bool = False

    type: QueryType = QueryType.WRITE

    def __init__(self, branch_name: str, edge_type: DatabaseEdgeType, batch_size: int, **kwargs: Any) -> None:
        self.branch_name = branch_name
        self.edge_type = edge_type
        self.batch_size = batch_size
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
MATCH (s)-[r:%(edge_type)s]->(d)
WHERE r.branch = $branch_name
WITH s, r, d
LIMIT $batch_size
DELETE r

WITH s, d
UNWIND [s, d] AS v
WITH DISTINCT v
WHERE NOT v:Root
AND NOT EXISTS { MATCH (v)--() }
DELETE v
        """ % {"edge_type": self.edge_type.value}
        self.params["branch_name"] = self.branch_name
        self.params["batch_size"] = self.batch_size
        self.add_to_query(query)

    def deleted_edge_count(self) -> int:
        return self.stats.get_counter("relationships_deleted")


class RebaseBranchQuery(Query):
    """Rebase a branch onto the default branch by updating edge timestamps.

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
    def __init__(
        self,
        exclude_global: bool = False,
        exclude_default: bool = False,
        exclude_terminal: bool = False,
        branch_filters: BranchListFilters | None = None,
        **kwargs: Any,
    ) -> None:
        self.branch_filters = branch_filters or BranchListFilters()
        self.exclude_global = exclude_global
        self.exclude_default = exclude_default
        self.exclude_terminal = exclude_terminal

        # Temporary storage for filter params (will be merged after super().__init__)
        self._branch_filter_params: dict[str, Any] = {}

        # Build raw_filter from branch_filters
        self.raw_filter = self._build_raw_filter()

        # Pass name/ids/partial_match to parent for existing handling
        super().__init__(
            ids=self.branch_filters.ids,
            node_name=self.branch_filters.name,
            partial_match=self.branch_filters.partial_match,
            **kwargs,
        )

        # Merge our filter params into the query params
        self.params.update(self._branch_filter_params)

    def _build_raw_filter(self) -> str:
        """Build Cypher WHERE clause conditions from branch_filters."""
        conditions: list[str] = []

        if self.exclude_terminal:
            terminal_values = ", ".join(f"'{status.value}'" for status in TERMINAL_BRANCH_STATUSES)
            conditions.append(f"NOT n.status IN [{terminal_values}]")
        else:
            # Always exclude DELETING branches
            conditions.append(f"n.status <> '{BranchStatus.DELETING.value}'")

        if self.exclude_global:
            conditions.append("n.is_global = false")

        if self.exclude_default:
            conditions.append("n.is_default = false")

        if self.branch_filters.status:
            param_name = "filter_status"
            self._branch_filter_params[param_name] = self.branch_filters.status.value
            conditions.append(f"n.status = ${param_name}")

        if self.branch_filters.created_by_id:
            param_name = "filter_created_by"
            self._branch_filter_params[param_name] = self.branch_filters.created_by_id
            conditions.append(f"n.created_by = ${param_name}")

        # Branched from (rebase timestamp) filters (with NULL check)
        if self.branch_filters.branched_from_after:
            param_name = "filter_branched_from_after"
            self._branch_filter_params[param_name] = Timestamp(
                self.branch_filters.branched_from_after.isoformat()
            ).to_string()
            conditions.append(f"(n.branched_from IS NOT NULL AND n.branched_from > ${param_name})")

        if self.branch_filters.branched_from_before:
            param_name = "filter_branched_from_before"
            self._branch_filter_params[param_name] = Timestamp(
                self.branch_filters.branched_from_before.isoformat()
            ).to_string()
            conditions.append(f"(n.branched_from IS NOT NULL AND n.branched_from < ${param_name})")

        if self.branch_filters.created_at_after:
            param_name = "filter_created_at_after"
            self._branch_filter_params[param_name] = Timestamp(
                self.branch_filters.created_at_after.isoformat()
            ).to_string()
            conditions.append(f"(n.created_at IS NOT NULL AND n.created_at > ${param_name})")

        if self.branch_filters.created_at_before:
            param_name = "filter_created_at_before"
            self._branch_filter_params[param_name] = Timestamp(
                self.branch_filters.created_at_before.isoformat()
            ).to_string()
            conditions.append(f"(n.created_at IS NOT NULL AND n.created_at < ${param_name})")

        if self.branch_filters.updated_at_after:
            param_name = "filter_updated_at_after"
            self._branch_filter_params[param_name] = Timestamp(
                self.branch_filters.updated_at_after.isoformat()
            ).to_string()
            conditions.append(f"(n.updated_at IS NOT NULL AND n.updated_at > ${param_name})")

        if self.branch_filters.updated_at_before:
            param_name = "filter_updated_at_before"
            self._branch_filter_params[param_name] = Timestamp(
                self.branch_filters.updated_at_before.isoformat()
            ).to_string()
            conditions.append(f"(n.updated_at IS NOT NULL AND n.updated_at < ${param_name})")

        return " AND ".join(conditions) if conditions else ""
