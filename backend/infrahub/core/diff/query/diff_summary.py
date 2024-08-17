from typing import Any

from pydantic import BaseModel
from typing_extensions import Self

from infrahub.core.query import Query, QueryResult, QueryType
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase

from .diff_get import QUERY_MATCH_NODES
from .filters import EnrichedDiffQueryFilters


# type: ignore[call-overload]
class DiffSummaryCounters(BaseModel):
    num_added: int = 0
    num_updated: int = 0
    num_unchanged: int = 0
    num_removed: int = 0
    num_conflicts: int = 0

    @classmethod
    def from_graph(cls, result: QueryResult) -> Self:
        return cls(
            num_added=int(result.get_as_str("num_added") or 0),
            num_updated=int(result.get_as_str("num_updated") or 0),
            num_unchanged=int(result.get_as_str("num_unchanged") or 0),
            num_removed=int(result.get_as_str("num_removed") or 0),
            num_conflicts=int(result.get_as_str("num_conflicts") or 0),
        )


class DiffSummaryQuery(Query):
    """Get a Summary of the diff"""

    name = "enriched_diff_summary"
    type = QueryType.READ
    insert_limit = False

    def __init__(
        self,
        base_branch_name: str,
        diff_branch_names: list[str],
        from_time: Timestamp,
        to_time: Timestamp,
        filters: EnrichedDiffQueryFilters,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.base_branch_name = base_branch_name
        self.diff_branch_names = diff_branch_names
        self.from_time = from_time
        self.to_time = to_time
        self.filters = filters or EnrichedDiffQueryFilters()

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        self.params = {
            "base_branch": self.base_branch_name,
            "diff_branches": self.diff_branch_names,
            "from_time": self.from_time.to_string(),
            "to_time": self.to_time.to_string(),
        }

        # ruff: noqa: E501
        self.add_to_query(query=QUERY_MATCH_NODES)

        if not self.filters.is_empty:
            filters, filter_params = self.filters.generate()
            self.params.update(filter_params)

            query_filters = """
            WHERE (
                %(filters)s
            )
            """ % {"filters": filters}
            self.add_to_query(query=query_filters)

        self.return_labels = [
            "SUM(diff_node.num_added) as num_added",
            "SUM(diff_node.num_updated) as num_updated",
            "SUM(diff_node.num_unchanged) as num_unchanged",
            "SUM(diff_node.num_removed) as num_removed",
            "SUM(diff_node.num_conflicts) as num_conflicts",
        ]

    def get_summary(self) -> DiffSummaryCounters:
        result = self.get_result()
        if not result:
            return DiffSummaryCounters()
        return DiffSummaryCounters.from_graph(result)