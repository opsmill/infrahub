from typing import Any

from infrahub.core.query import Query, QueryType
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase

from ..model.path import TimeRange


class EnrichedDiffTimeRangeQuery(Query):
    """
    Get the time ranges of all EnrichedDiffRoots for the given branches that are within the given timeframe in
    chronological order
    """

    name = "enriched_diff_time_ranges"
    type = QueryType.READ

    def __init__(
        self,
        base_branch_name: str,
        diff_branch_name: str,
        from_time: Timestamp,
        to_time: Timestamp,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.base_branch_name = base_branch_name
        self.diff_branch_name = diff_branch_name
        self.from_time = from_time
        self.to_time = to_time

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        self.params = {
            "base_branch": self.base_branch_name,
            "diff_branch": self.diff_branch_name,
            "from_time": self.from_time.to_string(),
            "to_time": self.to_time.to_string(),
        }
        query = """
        // get the roots of all diffs in the query
        MATCH (diff_root:DiffRoot)
        WHERE (diff_root.is_merged IS NULL OR diff_root.is_merged <> TRUE)
        AND diff_root.base_branch = $base_branch
        AND diff_root.diff_branch = $diff_branch
        AND diff_root.from_time >= $from_time
        AND diff_root.to_time <= $to_time
        WITH diff_root
        ORDER BY diff_root.base_branch, diff_root.diff_branch, diff_root.from_time, diff_root.to_time
        WITH diff_root.base_branch AS bb, diff_root.diff_branch AS db, collect(diff_root) AS same_branch_diff_roots
        WITH reduce(
            non_overlapping = [], dr in same_branch_diff_roots |
            CASE
                WHEN size(non_overlapping) = 0 THEN [dr]
                WHEN dr.from_time >= (non_overlapping[-1]).from_time AND dr.to_time <= (non_overlapping[-1]).to_time THEN non_overlapping
                WHEN (non_overlapping[-1]).from_time >= dr.from_time AND (non_overlapping[-1]).to_time <= dr.to_time THEN non_overlapping[..-1] + [dr]
                ELSE non_overlapping + [dr]
            END
        ) AS non_overlapping_diff_roots
        UNWIND non_overlapping_diff_roots AS diff_root
        """
        self.add_to_query(query=query)
        self.return_labels = [
            "diff_root.from_time AS from_time",
            "diff_root.to_time AS to_time",
        ]
        self.order_by = ["from_time ASC"]

    async def get_time_ranges(self) -> list[TimeRange]:
        time_ranges = []
        for result in self.get_results():
            from_time = Timestamp(str(result.get("from_time")))
            to_time = Timestamp(str(result.get("to_time")))
            time_ranges.append(TimeRange(from_time=from_time, to_time=to_time))

        return time_ranges
