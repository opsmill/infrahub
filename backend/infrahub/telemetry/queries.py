from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.query import Query, QueryType
from infrahub.core.query.standard_node import StandardNodeGetListQuery

if TYPE_CHECKING:
    from collections.abc import Generator

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
    """Count active nodes of the given kinds on the query's branch at the query's time.

    One pass over the graph replaces a per-kind count query fan-out; kinds with no
    active node return no row.
    """

    name = "count-nodes-by-kinds"
    type = QueryType.READ
    insert_return = False

    def __init__(self, kinds: list[str], **kwargs: Any) -> None:
        self.kinds = kinds
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
