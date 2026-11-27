from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.constants import NULL_VALUE
from infrahub.core.query import Query, QueryType
from infrahub.core.query.standard_node import StandardNodeGetListQuery

if TYPE_CHECKING:
    from collections.abc import Generator

    from infrahub.core.schema import NodeSchema
    from infrahub.database import InfrahubDatabase


def _normalize_start_date(value: str) -> str:
    """Expand a bare date (YYYY-MM-DD) to the start of that day in UTC."""
    if len(value) <= 10 and "T" not in value:
        return f"{value}T00:00:00.000000+00:00"
    return value


def _normalize_end_date(value: str) -> str:
    """Expand a bare date (YYYY-MM-DD) to the end of that day in UTC.

    `created_at` is stored as a full ISO timestamp (e.g. ``2026-04-10T14:30:00.123456+00:00``).
    A naive lexicographic compare against ``end_date="2026-04-10"`` would exclude every
    snapshot collected later that day. Expanding the bare date to ``T23:59:59.999999+00:00``
    makes the upper bound day-inclusive.
    """
    if len(value) <= 10 and "T" not in value:
        return f"{value}T23:59:59.999999+00:00"
    return value


@dataclass(frozen=True)
class NodeKindCount:
    kind: str
    count: int


class CountNodesByKindsQuery(Query):
    """Count active nodes of the given concrete kinds on the query's branch at the query's time.

    One pass over the graph replaces a per-kind count query fan-out; kinds with no
    active node return no row.

    Concrete node schemas only: the match is on the vertex ``kind`` property, which
    always holds the node's concrete kind. A generic kind never appears there (it is
    carried only in the vertex labels), so matching a generic would silently count
    zero. Supporting generics would require matching on labels instead, and a sum over
    label matches double-counts nodes inheriting several of the requested kinds.
    """

    name = "count-nodes-by-kinds"
    type = QueryType.READ
    insert_return = False

    def __init__(self, schemas: list[NodeSchema], **kwargs: Any) -> None:
        self.kinds = [schema.kind for schema in schemas]
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at)
        self.params.update(branch_params)
        self.params["kinds"] = self.kinds

        query = """
        MATCH (n:Node)
        WHERE n.kind IN $kinds
        CALL (n) {
            MATCH (n)-[r:IS_PART_OF]->(:Root)
            WHERE %(branch_filter)s
            RETURN r
            // r.status is a tie-breaker for nodes added/deleted at the same time
            ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
            LIMIT 1
        }
        WITH n, r
        WHERE r.status = "active"
        RETURN n.kind AS kind, count(n) AS total
        ORDER BY kind
        """ % {"branch_filter": branch_filter}
        self.add_to_query(query)
        self.update_return_labels(["kind", "total"])

    def get_data(self) -> Generator[NodeKindCount, None, None]:
        for result in self.get_results():
            yield NodeKindCount(
                kind=result.get_as_type("kind", str),
                count=result.get_as_type("total", int),
            )


@dataclass(frozen=True)
class NodesWithOutputCount:
    nodes: int
    nodes_with_content: int
    outputs_with_content: int


class CountNodesWithOutputQuery(Query):
    """Count the nodes that have at least one active node of an output kind, on the query's branch at the query's time.

    A target can have several nodes of the output kind, each linked to it by one relationship.
    With a content attribute, the query also counts the outputs whose attribute has a value and
    the nodes that have at least one of them.
    """

    name = "count-nodes-with-output"
    type = QueryType.READ
    insert_return = False

    def __init__(
        self, output_kind: str, relationship_identifier: str, content_attribute: str | None = None, **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at)
        self.params.update(branch_params)
        self.params["relationship_identifier"] = relationship_identifier

        content_query = "WITH output, target, 0 AS has_content"
        if content_attribute:
            self.params["content_attribute"] = content_attribute
            self.params["null_value"] = NULL_VALUE
            content_query = """
        CALL (output) {
            OPTIONAL MATCH (output)-[r1:HAS_ATTRIBUTE]->(:Attribute {name: $content_attribute})-[r2:HAS_VALUE]->(av)
            WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
            RETURN av.value AS content, r1.status = "active" AND r2.status = "active" AS content_is_active
            ORDER BY r2.branch_level DESC, r2.from DESC, r2.status ASC
            LIMIT 1
        }
        WITH output, target,
            CASE WHEN content_is_active AND content IS NOT NULL AND content <> $null_value THEN 1 ELSE 0 END AS has_content
            """ % {"branch_filter": branch_filter}

        query = """
        MATCH (output:%(output_kind)s)
        CALL (output) {
            MATCH (output)-[r:IS_PART_OF]->(:Root)
            WHERE %(branch_filter)s
            RETURN r.status = "active" AS output_is_active
            ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
            LIMIT 1
        }
        WITH output, output_is_active
        WHERE output_is_active
        MATCH (output)-[:IS_RELATED]->(rl:Relationship {name: $relationship_identifier})
        WITH DISTINCT output, rl
        CALL (output, rl) {
            MATCH (output)-[r1:IS_RELATED]->(rl)<-[r2:IS_RELATED]-(target:Node)
            WHERE target.uuid <> output.uuid
                AND all(r IN [r1, r2] WHERE (%(branch_filter)s))
            RETURN target, r1.status = "active" AND r2.status = "active" AS is_related
            // status is a tie-breaker for an edge added and deleted at the same time
            ORDER BY r1.branch_level + r2.branch_level DESC, r2.from DESC, r2.status ASC, r1.from DESC, r1.status ASC
            LIMIT 1
        }
        WITH output, target, is_related
        WHERE is_related
        CALL (target) {
            MATCH (target)-[r:IS_PART_OF]->(:Root)
            WHERE %(branch_filter)s
            RETURN r.status = "active" AS target_is_active
            ORDER BY r.branch_level DESC, r.from DESC, r.status ASC
            LIMIT 1
        }
        WITH output, target, target_is_active
        WHERE target_is_active
        %(content_query)s
        WITH target.uuid AS target_id, sum(has_content) AS outputs_with_content
        RETURN count(target_id) AS nodes,
            sum(CASE WHEN outputs_with_content > 0 THEN 1 ELSE 0 END) AS nodes_with_content,
            sum(outputs_with_content) AS outputs_with_content
        """ % {"output_kind": output_kind, "branch_filter": branch_filter, "content_query": content_query}
        self.add_to_query(query)
        self.return_labels = ["nodes", "nodes_with_content", "outputs_with_content"]

    def get_data(self) -> NodesWithOutputCount:
        result = self.get_result()
        if result is None:
            return NodesWithOutputCount(nodes=0, nodes_with_content=0, outputs_with_content=0)
        return NodesWithOutputCount(
            nodes=result.get_as_type("nodes", int),
            nodes_with_content=result.get_as_type("nodes_with_content", int),
            outputs_with_content=result.get_as_type("outputs_with_content", int),
        )


class TelemetrySnapshotGetListQuery(StandardNodeGetListQuery):
    name = "telemetry-snapshot-get-list"

    def __init__(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        **kwargs: Any,
    ) -> None:
        self._start_date = start_date
        self._end_date = end_date
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        filters: list[str] = []
        params: dict[str, Any] = {}

        if self._start_date:
            filters.append("n.created_at >= $start_date")
            params["start_date"] = _normalize_start_date(self._start_date)
        if self._end_date:
            filters.append("n.created_at <= $end_date")
            params["end_date"] = _normalize_end_date(self._end_date)

        if filters:
            self.raw_filter = " AND ".join(filters)

        await super().query_init(db=db, **kwargs)
        self.params.update(params)
