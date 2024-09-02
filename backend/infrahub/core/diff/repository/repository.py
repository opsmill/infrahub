from infrahub import config
from infrahub.core import registry
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ResourceNotFoundError

from ..model.path import ConflictSelection, EnrichedDiffConflict, EnrichedDiffRoot, TimeRange, TrackingId
from ..query.delete_query import EnrichedDiffDeleteQuery
from ..query.diff_get import EnrichedDiffGetQuery
from ..query.diff_summary import DiffSummaryCounters, DiffSummaryQuery
from ..query.filters import EnrichedDiffQueryFilters
from ..query.get_conflict_query import EnrichedDiffConflictQuery
from ..query.save_query import EnrichedDiffSaveQuery
from ..query.time_range_query import EnrichedDiffTimeRangeQuery
from ..query.update_conflict_query import EnrichedDiffConflictUpdateQuery
from .deserializer import EnrichedDiffDeserializer


class DiffRepository:
    def __init__(self, db: InfrahubDatabase, deserializer: EnrichedDiffDeserializer):
        self.db = db
        self.deserializer = deserializer

    async def get(
        self,
        base_branch_name: str,
        diff_branch_names: list[str],
        from_time: Timestamp | None = None,
        to_time: Timestamp | None = None,
        filters: dict | None = None,
        include_parents: bool = True,
        limit: int | None = None,
        offset: int | None = None,
        tracking_id: TrackingId | None = None,
        include_empty: bool = False,
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
            tracking_id=tracking_id,
        )
        await query.execute(db=self.db)
        diff_roots = await self.deserializer.deserialize(
            database_results=query.get_results(), include_parents=include_parents
        )
        if not include_empty:
            diff_roots = [dr for dr in diff_roots if len(dr.nodes) > 0]
        return diff_roots

    async def get_one(
        self, tracking_id: TrackingId, diff_branch_name: str, filters: dict | None = None, include_parents: bool = True
    ) -> EnrichedDiffRoot:
        enriched_diffs = await self.get(
            base_branch_name=registry.default_branch,
            diff_branch_names=[diff_branch_name],
            tracking_id=tracking_id,
            filters=filters,
            include_parents=include_parents,
        )
        if len(enriched_diffs) == 0:
            raise ResourceNotFoundError(
                f"Cannot find diff for branch {diff_branch_name} and tracking_id {tracking_id.serialize()}"
            )
        if len(enriched_diffs) > 1:
            raise ResourceNotFoundError(
                f"Multiple diffs for branch {diff_branch_name} and tracking_id {tracking_id.serialize()}"
            )
        return enriched_diffs[0]

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

    async def delete_diff_roots(self, diff_root_uuids: list[str]) -> None:
        query = await EnrichedDiffDeleteQuery.init(db=self.db, enriched_diff_root_uuids=diff_root_uuids)
        await query.execute(db=self.db)

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

    async def get_conflict_by_id(self, conflict_id: str) -> EnrichedDiffConflict:
        query = await EnrichedDiffConflictQuery.init(db=self.db, conflict_id=conflict_id)
        await query.execute(db=self.db)
        conflict_node = await query.get_conflict_node()
        if not conflict_node:
            raise ResourceNotFoundError(f"No conflict with id {conflict_id}")
        return self.deserializer.deserialize_conflict(diff_conflict_node=conflict_node)

    async def update_conflict_by_id(
        self, conflict_id: str, selection: ConflictSelection | None
    ) -> EnrichedDiffConflict:
        query = await EnrichedDiffConflictUpdateQuery.init(db=self.db, conflict_id=conflict_id, selection=selection)
        await query.execute(db=self.db)
        conflict_node = await query.get_conflict_node()
        if not conflict_node:
            raise ResourceNotFoundError(f"No conflict with id {conflict_id}")
        return self.deserializer.deserialize_conflict(diff_conflict_node=conflict_node)
