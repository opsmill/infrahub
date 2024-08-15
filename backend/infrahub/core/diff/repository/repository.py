from infrahub import config
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase

from ..model.path import EnrichedDiffRoot, TimeRange
from ..query.diff_get import EnrichedDiffGetQuery
from ..query.diff_summary import DiffSummaryCounters, DiffSummaryQuery
from ..query.filters import EnrichedDiffQueryFilters
from .save_query import EnrichedDiffSaveQuery
from .time_range_query import EnrichedDiffTimeRangeQuery


class DiffRepository:
    def __init__(self, db: InfrahubDatabase):
        self.db = db

    async def get(
        self,
        base_branch_name: str,
        diff_branch_names: list[str],
        from_time: Timestamp,
        to_time: Timestamp,
        filters: dict | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[EnrichedDiffRoot]:
        final_max_depth = config.SETTINGS.database.max_depth_search_hierarchy
        final_limit = limit or config.SETTINGS.database.query_size_limit
        query = await EnrichedDiffGetQuery.init(
            db=self.db,
            base_branch_name=base_branch_name,
            diff_branch_names=diff_branch_names,
            from_time=from_time,
            to_time=to_time,
            filters=EnrichedDiffQueryFilters(**dict(filters or {})),
            max_depth=final_max_depth,
            limit=final_limit,
            offset=offset,
        )
        await query.execute(db=self.db)
        diff_roots = await query.get_enriched_diff_roots()
        diff_roots = [dr for dr in diff_roots if len(dr.nodes) > 0]
        return diff_roots

    async def save(self, enriched_diff: EnrichedDiffRoot) -> None:
        query = await EnrichedDiffSaveQuery.init(db=self.db, enriched_diff_root=enriched_diff)
        await query.execute(db=self.db)

    async def summary(
        self,
        base_branch_name: str,
        diff_branch_names: list[str],
        from_time: Timestamp,
        to_time: Timestamp,
        filters: dict | None = None,
    ) -> DiffSummaryCounters:
        query = await DiffSummaryQuery.init(
            db=self.db,
            base_branch_name=base_branch_name,
            diff_branch_names=diff_branch_names,
            from_time=from_time,
            to_time=to_time,
            filters=EnrichedDiffQueryFilters(**dict(filters or {})),
        )
        await query.execute(db=self.db)
        return query.get_summary()

    async def get_time_ranges(
        self,
        base_branch_name: str,
        diff_branch_name: str,
        from_time: Timestamp,
        to_time: Timestamp,
    ) -> list[TimeRange]:
        query = await EnrichedDiffTimeRangeQuery.init(
            db=self.db,
            base_branch_name=base_branch_name,
            diff_branch_name=diff_branch_name,
            from_time=from_time,
            to_time=to_time,
        )
        await query.execute(db=self.db)
        return await query.get_time_ranges()
