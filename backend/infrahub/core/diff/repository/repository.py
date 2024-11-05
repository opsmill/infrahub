from typing import Generator

from infrahub import config
from infrahub.core import registry
from infrahub.core.diff.query.field_summary import EnrichedDiffNodeFieldSummaryQuery
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase, retry_db_transaction
from infrahub.exceptions import ResourceNotFoundError

from ..model.path import (
    ConflictSelection,
    EnrichedDiffConflict,
    EnrichedDiffRoot,
    EnrichedDiffs,
    EnrichedNodeCreateRequest,
    NodeDiffFieldSummary,
    TimeRange,
    TrackingId,
)
from ..query.delete_query import EnrichedDiffDeleteQuery
from ..query.diff_get import EnrichedDiffGetQuery
from ..query.diff_summary import DiffSummaryCounters, DiffSummaryQuery
from ..query.empty_roots import EnrichedDiffEmptyRootsQuery
from ..query.filters import EnrichedDiffQueryFilters
from ..query.get_conflict_query import EnrichedDiffConflictQuery
from ..query.save import EnrichedDiffRootsCreateQuery, EnrichedNodeBatchCreateQuery, EnrichedNodesLinkQuery
from ..query.time_range_query import EnrichedDiffTimeRangeQuery
from ..query.update_conflict_query import EnrichedDiffConflictUpdateQuery
from .deserializer import EnrichedDiffDeserializer


class DiffRepository:
    MAX_SAVE_BATCH_SIZE: int = 100

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
        diff_ids: list[str] | None = None,
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
            diff_ids=diff_ids,
        )
        await query.execute(db=self.db)
        diff_roots = await self.deserializer.deserialize(
            database_results=query.get_results(), include_parents=include_parents
        )
        if not include_empty:
            diff_roots = [dr for dr in diff_roots if len(dr.nodes) > 0]
        return diff_roots

    async def get_pairs(
        self,
        base_branch_name: str,
        diff_branch_name: str,
        from_time: Timestamp,
        to_time: Timestamp,
    ) -> list[EnrichedDiffs]:
        max_depth = config.SETTINGS.database.max_depth_search_hierarchy
        query = await EnrichedDiffGetQuery.init(
            db=self.db,
            base_branch_name=base_branch_name,
            diff_branch_names=[diff_branch_name],
            from_time=from_time,
            to_time=to_time,
            max_depth=max_depth,
        )
        await query.execute(db=self.db)
        diff_branch_roots = await self.deserializer.deserialize(
            database_results=query.get_results(), include_parents=True
        )
        diffs_by_uuid = {dbr.uuid: dbr for dbr in diff_branch_roots}
        base_partner_query = await EnrichedDiffGetQuery.init(
            db=self.db,
            base_branch_name=base_branch_name,
            diff_branch_names=[base_branch_name],
            max_depth=max_depth,
            diff_ids=[d.partner_uuid for d in diffs_by_uuid.values()],
        )
        await base_partner_query.execute(db=self.db)
        base_branch_roots = await self.deserializer.deserialize(
            database_results=base_partner_query.get_results(), include_parents=True
        )
        diffs_by_uuid.update({bbr.uuid: bbr for bbr in base_branch_roots})
        return [
            EnrichedDiffs(
                base_branch_name=base_branch_name,
                diff_branch_name=diff_branch_name,
                base_branch_diff=diffs_by_uuid[dbr.partner_uuid],
                diff_branch_diff=dbr,
            )
            for dbr in diff_branch_roots
        ]

    async def get_one(
        self,
        diff_branch_name: str,
        tracking_id: TrackingId | None = None,
        diff_id: str | None = None,
        filters: dict | None = None,
        include_parents: bool = True,
    ) -> EnrichedDiffRoot:
        enriched_diffs = await self.get(
            base_branch_name=registry.default_branch,
            diff_branch_names=[diff_branch_name],
            tracking_id=tracking_id,
            diff_ids=[diff_id] if diff_id else None,
            filters=filters,
            include_parents=include_parents,
            include_empty=True,
        )
        error_str = f"branch {diff_branch_name}"
        if tracking_id:
            error_str += f" with tracking_id {tracking_id.serialize()}"
        if diff_id:
            error_str += f" with ID {diff_id}"
        if len(enriched_diffs) == 0:
            raise ResourceNotFoundError(f"Cannot find diff for {error_str}")
        if len(enriched_diffs) > 1:
            raise ResourceNotFoundError(f"Multiple diffs for {error_str}")
        return enriched_diffs[0]

    def _get_node_create_request_batch(
        self, enriched_diffs: EnrichedDiffs
    ) -> Generator[list[EnrichedNodeCreateRequest], None, None]:
        node_requests = []
        for diff_root in (enriched_diffs.base_branch_diff, enriched_diffs.diff_branch_diff):
            for node in diff_root.nodes:
                node_requests.append(EnrichedNodeCreateRequest(node=node, root_uuid=diff_root.uuid))
                if len(node_requests) == self.MAX_SAVE_BATCH_SIZE:
                    yield node_requests
                    node_requests = []
        if node_requests:
            yield node_requests

    @retry_db_transaction(name="enriched_diff_save")
    async def save(self, enriched_diffs: EnrichedDiffs) -> None:
        root_query = await EnrichedDiffRootsCreateQuery.init(db=self.db, enriched_diffs=enriched_diffs)
        await root_query.execute(db=self.db)
        for node_create_batch in self._get_node_create_request_batch(enriched_diffs=enriched_diffs):
            node_query = await EnrichedNodeBatchCreateQuery.init(db=self.db, node_create_batch=node_create_batch)
            await node_query.execute(db=self.db)
        link_query = await EnrichedNodesLinkQuery.init(db=self.db, enriched_diffs=enriched_diffs)
        await link_query.execute(db=self.db)

    async def summary(
        self,
        base_branch_name: str,
        diff_branch_names: list[str],
        from_time: Timestamp,
        to_time: Timestamp,
        filters: dict | None = None,
    ) -> DiffSummaryCounters | None:
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

    async def get_empty_roots(
        self,
        diff_branch_names: list[str] | None = None,
        base_branch_names: list[str] | None = None,
    ) -> list[EnrichedDiffRoot]:
        query = await EnrichedDiffEmptyRootsQuery.init(
            db=self.db, diff_branch_names=diff_branch_names, base_branch_names=base_branch_names
        )
        await query.execute(db=self.db)
        diff_roots = []
        for neo4j_node in query.get_empty_root_nodes():
            diff_roots.append(self.deserializer.build_diff_root(root_node=neo4j_node))
        return diff_roots

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

    async def get_node_field_summaries(
        self, diff_branch_name: str, tracking_id: TrackingId | None = None, diff_id: str | None = None
    ) -> list[NodeDiffFieldSummary]:
        query = await EnrichedDiffNodeFieldSummaryQuery.init(
            db=self.db, diff_branch_name=diff_branch_name, tracking_id=tracking_id, diff_id=diff_id
        )
        await query.execute(db=self.db)
        return await query.get_field_summaries()
