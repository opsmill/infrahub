from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.constants import NODE_KIND_REGEX
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence

    from infrahub.core.constants import RelationshipDirection
    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class KindLabelCountQueryResult:
    kind: str
    count: int


class KindLabelCountQuery(Query):
    """Count the vertices that carry each kind label, deleted vertices and vertices of every branch included.

    A label cannot be a query parameter, so each kind is written into the query text as a label, and the
    constructor accepts only names shaped like a schema kind.
    """

    name = "graphql-cost-kind-label-count"
    type = QueryType.READ
    insert_return = False

    def __init__(self, kinds: Sequence[str], **kwargs: Any) -> None:
        if not kinds:
            raise ValueError("Counting kind labels needs at least one kind")
        invalid_kinds = sorted(kind for kind in kinds if not re.fullmatch(NODE_KIND_REGEX, kind))
        if invalid_kinds:
            raise ValueError(f"Only kind names can be used as labels, not: {', '.join(invalid_kinds)}")
        self.kinds = sorted(set(kinds))
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        label_counts: list[str] = []
        for index, kind in enumerate(self.kinds):
            self.params[f"kind_{index}"] = kind
            label_counts.append(f"MATCH (n:`{kind}`) RETURN $kind_{index} AS kind, count(n) AS total")
        query = """
        CALL () {
            %(label_counts)s
        }
        RETURN kind, total
        """ % {"label_counts": "\nUNION ALL\n".join(label_counts)}
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
        MATCH (n:Node)
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
