from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.constants import NODE_KIND_REGEX
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.order import OrderModel
from infrahub.core.query import Query, QueryType
from infrahub.core.query.node import NodeGetListQuery
from infrahub.core.query.relationship import RelationshipGetPeerQuery

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence

    from infrahub.core.constants import RelationshipDirection
    from infrahub.core.schema import NodeSchema, RelationshipSchema
    from infrahub.database import InfrahubDatabase


def _label_count_subquery(kinds: Sequence[str], params: dict[str, Any]) -> str:
    """Return the branches of a union that yields one `label_kind` and `label_total` row for each kind.

    A label cannot be a query parameter, so each kind is written into the query text as a label, and only names
    shaped like a schema kind are accepted.

    Raises:
        ValueError: When no kind is given, or a kind is not shaped like a schema kind.

    """
    if not kinds:
        raise ValueError("Counting kind labels needs at least one kind")
    invalid_kinds = sorted(kind for kind in kinds if not re.fullmatch(NODE_KIND_REGEX, kind))
    if invalid_kinds:
        raise ValueError(f"Only kind names can be used as labels, not: {', '.join(invalid_kinds)}")
    label_counts: list[str] = []
    for index, kind in enumerate(sorted(set(kinds))):
        params[f"label_kind_{index}"] = kind
        # An aggregation without a grouping key is read from the database's label counts, not a scan of the label.
        label_counts.append(
            f"MATCH (labelled:`{kind}`) WITH count(labelled) AS label_total "
            f"RETURN $label_kind_{index} AS label_kind, label_total"
        )
    return "\nUNION ALL\n".join(label_counts)


@dataclass(frozen=True)
class KindLabelCountQueryResult:
    kind: str
    count: int


class KindLabelCountQuery(Query):
    """Count the vertices that carry each kind label, deleted vertices and vertices of every branch included."""

    name = "graphql-cost-kind-label-count"
    type = QueryType.READ
    insert_return = False

    def __init__(self, kinds: Sequence[str], **kwargs: Any) -> None:
        self.kinds = sorted(set(kinds))
        # One row comes back for each kind, so a limit of that many rows runs the query once instead of in pages.
        kwargs["limit"] = len(self.kinds)
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        query = """
        CALL () {
            %(label_counts)s
        }
        RETURN label_kind AS kind, label_total AS total
        """ % {"label_counts": _label_count_subquery(kinds=self.kinds, params=self.params)}
        self.add_to_query(query)
        self.return_labels = ["kind", "total"]
        self.order_by = ["kind"]

    def get_data(self) -> Generator[KindLabelCountQueryResult, None, None]:
        for result in self.get_results():
            yield KindLabelCountQueryResult(
                kind=result.get_as_type("kind", str), count=result.get_as_type("total", int)
            )


@dataclass(frozen=True)
class KindActiveNodeIdsQueryResult:
    node_id: str
    is_active: bool
    """The latest edge between the node and the root is active on the branch at the query's time."""


class KindActiveNodeIdsQuery(Query):
    """Read one page of the nodes of a concrete kind, each with whether it is active on the branch.

    The page is taken before the edge to the root is resolved, so each run resolves it for one page of nodes
    only; inactive nodes keep their row, so a page shorter than the limit is the last one.
    """

    name = "graphql-cost-kind-active-node-ids"
    type = QueryType.READ
    insert_return = False
    insert_limit = False

    def __init__(self, kind: str, limit: int, **kwargs: Any) -> None:
        self.kind = kind
        super().__init__(limit=limit, **kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at)
        self.params.update(branch_params)
        self.params["kind"] = self.kind
        self.params["page_offset"] = self.offset or 0
        self.params["page_limit"] = self.limit
        query = """
        MATCH (n:Node {kind: $kind})
        WITH n
        ORDER BY n.uuid, %(id_func)s(n)
        SKIP $page_offset
        LIMIT $page_limit
        CALL (n) {
            OPTIONAL MATCH (n)-[r:IS_PART_OF]->(:Root)
            WHERE %(branch_filter)s
            RETURN r
            // r.status is a tie-breaker for nodes added and deleted at the same time
            ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
            LIMIT 1
        }
        RETURN n.uuid AS node_id, coalesce(r.status = "active", false) AS is_active
        """ % {"branch_filter": branch_filter, "id_func": db.get_id_function_name()}
        self.add_to_query(query)
        self.return_labels = ["node_id", "is_active"]

    def get_data(self) -> Generator[KindActiveNodeIdsQueryResult, None, None]:
        for result in self.get_results():
            yield KindActiveNodeIdsQueryResult(
                node_id=result.get_as_type("node_id", str), is_active=result.get_as_type("is_active", bool)
            )


@dataclass(frozen=True)
class RelationshipSideDegreeQueryResult:
    node_id: str
    peer_kind: str
    """Concrete kind of the peers."""

    peers: int


class RelationshipSideDegreeQuery(Query):
    """Count the active peers of the given nodes through one side of a relationship, for each concrete peer kind.

    A peer counts when the latest of each of the two edges that join the node to it is active on the branch,
    the rule the relationship fields apply to the peers they return. A node without an active peer has no row.
    """

    name = "graphql-cost-relationship-side-degree"
    type = QueryType.READ
    insert_return = False

    def __init__(
        self,
        kind: str,
        node_ids: Sequence[str],
        identifier: str,
        direction: RelationshipDirection,
        **kwargs: Any,
    ) -> None:
        self.kind = kind
        self.node_ids = list(node_ids)
        self.identifier = identifier
        self.direction = direction
        kwargs.pop("limit", None)
        kwargs.pop("offset", None)
        # The rows come back in one aggregated record, and a set limit makes the query run once instead of in pages.
        super().__init__(limit=1, **kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at)
        self.params.update(branch_params)
        self.params["node_ids"] = self.node_ids
        self.params["kind"] = self.kind
        self.params["identifier"] = self.identifier
        arrows = self.get_query_arrows(direction=self.direction)
        query = """
        // without the hint, a chunk of ids is planned as a read of every node of the kind through the kind index
        MATCH (n:Node)
        USING INDEX n:Node(uuid)
        WHERE n.uuid IN $node_ids AND n.kind = $kind
        MATCH (n)%(left_start)s[:IS_RELATED]%(left_end)s(rl:Relationship { name: $identifier })
        WITH DISTINCT n, rl
        CALL (n, rl) {
            MATCH path = (n)%(left_start)s[r1:IS_RELATED]%(left_end)s(rl)%(right_start)s[r2:IS_RELATED]%(right_end)s(peer:Node)
            WHERE peer.uuid <> n.uuid AND all(r IN [r1, r2] WHERE (%(branch_filter)s))
            WITH peer, r1, r2, reduce(br_lvl = 0, r IN relationships(path) | br_lvl + r.branch_level) AS branch_level
            RETURN peer, r1.status = "active" AND r2.status = "active" AS is_active
            // status is a tie-breaker for nodes whose kind was migrated
            ORDER BY branch_level DESC, r2.from DESC, r2.status ASC, r1.from DESC, r1.status ASC
            LIMIT 1
        }
        WITH n, peer, is_active
        WHERE is_active
        WITH n.uuid AS node_id, peer.kind AS peer_kind, count(DISTINCT peer) AS peers
        RETURN collect({node_id: node_id, peer_kind: peer_kind, peers: peers}) AS degrees
        """ % {
            "left_start": arrows.left.start,
            "left_end": arrows.left.end,
            "right_start": arrows.right.start,
            "right_end": arrows.right.end,
            "branch_filter": branch_filter,
        }
        self.add_to_query(query)
        self.return_labels = ["degrees"]

    def get_data(self) -> Generator[RelationshipSideDegreeQueryResult, None, None]:
        result = self.get_result()
        if result is None:
            return
        yield from result.get_as_list_of_type("degrees", RelationshipSideDegreeQueryResult)


@dataclass(frozen=True)
class FirstStepKindNodesQueryResult:
    kind: str
    """Concrete kind of the nodes."""

    node_count: int
    node_ids: list[str]
    """IDs of the nodes, at most the ID limit of the query."""


@dataclass(frozen=True)
class FirstStepLabelCountQueryResult:
    kind: str
    count: int


@dataclass(frozen=True)
class FirstStepNodesQueryResult:
    kinds: tuple[FirstStepKindNodesQueryResult, ...]
    """One entry for each concrete kind with nodes."""

    label_counts: tuple[FirstStepLabelCountQueryResult, ...]


class FirstStepNodesQuery(NodeGetListQuery):
    """Count the nodes that a top-level field returns, for each concrete kind, with their IDs.

    The nodes are matched with the filters, order, offset and limit of the list query of the field, and the
    current label count of each given kind comes back in the same result.
    """

    name = "graphql-cost-first-step-nodes"
    insert_return = False

    def __init__(
        self,
        schema: NodeSchema,
        filters: dict[str, Any] | None,
        partial_match: bool,
        order: OrderModel | None,
        node_offset: int | None,
        node_limit: int | None,
        id_limit: int,
        label_count_kinds: Sequence[str],
        **kwargs: Any,
    ) -> None:
        """Prepare the count of the nodes of a top-level field.

        Args:
            node_offset: Offset of the field; None or 0 for no offset.
            node_limit: Limit of the field; None or 0 for no limit, as the list query reads it.
            id_limit: Most node IDs returned for each kind.
            label_count_kinds: Kinds whose current label count is returned; empty for none.

        """
        kwargs.pop("limit", None)
        kwargs.pop("offset", None)
        self.node_offset = node_offset or 0
        self.node_limit = node_limit or None
        self.id_limit = id_limit
        self.label_count_kinds = sorted(set(label_count_kinds))
        # Without an offset or a limit, the order does not change which nodes are counted.
        has_window = bool(self.node_offset or self.node_limit)
        super().__init__(
            schema=schema,
            filters=filters,
            partial_match=partial_match,
            order=order if has_window else OrderModel(disable=True),
            **kwargs,
        )
        # The counts come back in one row, and a set limit makes the query run once instead of in pages.
        self.limit = 1

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        await super().query_init(db=db, **kwargs)
        if self.node_offset or self.node_limit:
            self.params["first_step_offset"] = self.node_offset
            window = "WITH %(variables)s ORDER BY %(order)s SKIP $first_step_offset" % {
                "variables": ", ".join(self._get_tracked_variables()),
                "order": ", ".join(self.order_by or ["n.uuid"]),
            }
            if self.node_limit:
                self.params["first_step_limit"] = self.node_limit
                window += " LIMIT $first_step_limit"
            self.add_to_query(window)
        self.order_by = []

        self.params["first_step_id_limit"] = self.id_limit
        query = """
        WITH n.kind AS kind, n.uuid AS node_id
        WITH kind, count(node_id) AS node_count, collect(node_id)[..$first_step_id_limit] AS node_ids
        WITH collect({kind: kind, node_count: node_count, node_ids: node_ids}) AS kinds
        """
        self.add_to_query(query)
        if self.label_count_kinds:
            label_counts_query = """
            CALL () {
                CALL () {
                    %(label_counts)s
                }
                RETURN collect({kind: label_kind, count: label_total}) AS label_counts
            }
            """ % {"label_counts": _label_count_subquery(kinds=self.label_count_kinds, params=self.params)}
            self.add_to_query(label_counts_query)
        else:
            self.add_to_query("WITH kinds, [] AS label_counts")
        self.add_to_query("RETURN kinds, label_counts")
        self.return_labels = ["kinds", "label_counts"]

    def get_data(self) -> FirstStepNodesQueryResult:
        result = self.get_result()
        if result is None:
            return FirstStepNodesQueryResult(kinds=(), label_counts=())
        return FirstStepNodesQueryResult(
            kinds=tuple(result.get_as_list_of_type("kinds", FirstStepKindNodesQueryResult)),
            label_counts=tuple(result.get_as_list_of_type("label_counts", FirstStepLabelCountQueryResult)),
        )


@dataclass(frozen=True)
class FirstStepPeerCountQueryResult:
    peer_kind: str
    """Concrete kind of the peers."""

    paths: int
    """Pairs of a source node and one of its peers of this kind."""

    distinct_peers: int
    max_parents: int
    """Largest number of source nodes that reach one peer of this kind."""


class FirstStepPeerCountQuery(RelationshipGetPeerQuery):
    """Count, for each concrete peer kind, the peers that a relationship field returns for the given source nodes.

    The peers are matched with the filters and the active-edge rule of the peer query of the field, without its
    offset and limit.
    """

    name = "graphql-cost-first-step-peer-count"
    insert_return = False

    def __init__(
        self, source_ids: Sequence[str], schema: RelationshipSchema, filters: dict[str, Any], **kwargs: Any
    ) -> None:
        kwargs.pop("limit", None)
        kwargs.pop("offset", None)
        super().__init__(
            source_ids=list(source_ids),
            schema=schema,
            filters=filters,
            rel_type=DatabaseEdgeType.IS_RELATED.value,
            requested_order=OrderModel(disable=True),
            # The counts come back in one row, and a set limit makes the query run once instead of in pages.
            limit=1,
            **kwargs,
        )

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        await super().query_init(db=db, **kwargs)
        self.order_by = []
        query = """
        WITH DISTINCT source_node.uuid AS source_id, peer.uuid AS peer_id, peer.kind AS peer_kind
        WITH peer_kind, peer_id, count(source_id) AS parents
        WITH peer_kind, sum(parents) AS paths, count(peer_id) AS distinct_peers, max(parents) AS max_parents
        RETURN collect({
            peer_kind: peer_kind, paths: paths, distinct_peers: distinct_peers, max_parents: max_parents
        }) AS peer_counts
        """
        self.add_to_query(query)
        self.return_labels = ["peer_counts"]

    def get_data(self) -> Generator[FirstStepPeerCountQueryResult, None, None]:
        result = self.get_result()
        if result is None:
            return
        yield from result.get_as_list_of_type("peer_counts", FirstStepPeerCountQueryResult)
