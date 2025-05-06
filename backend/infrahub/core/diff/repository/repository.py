from typing import AsyncGenerator, Generator, Iterable

from neo4j.exceptions import TransientError

from infrahub import config
from infrahub.core import registry
from infrahub.core.diff.query.drop_nodes import EnrichedDiffDropNodesQuery
from infrahub.core.diff.query.field_summary import EnrichedDiffNodeFieldSummaryQuery
from infrahub.core.diff.query.summary_counts_enricher import (
    DiffFieldsSummaryCountsEnricherQuery,
    DiffNodesSummaryCountsEnricherQuery,
)
from infrahub.core.query.diff import DiffCountChanges
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase, retry_db_transaction
from infrahub.exceptions import ResourceNotFoundError
from infrahub.log import get_logger

from ..model.field_specifiers_map import NodeFieldSpecifierMap
from ..model.path import (
    ConflictSelection,
    EnrichedDiffConflict,
    EnrichedDiffNode,
    EnrichedDiffRoot,
    EnrichedDiffRootMetadata,
    EnrichedDiffs,
    EnrichedDiffsMetadata,
    EnrichedNodeCreateRequest,
    NodeDiffFieldSummary,
    NodeIdentifier,
    TimeRange,
    TrackingId,
)
from ..query.all_conflicts import EnrichedDiffAllConflictsQuery
from ..query.delete_query import EnrichedDiffDeleteQuery
from ..query.diff_get import EnrichedDiffGetQuery
from ..query.diff_summary import DiffSummaryCounters, DiffSummaryQuery
from ..query.field_specifiers import EnrichedDiffFieldSpecifiersQuery
from ..query.filters import EnrichedDiffQueryFilters
from ..query.get_conflict_query import EnrichedDiffConflictQuery
from ..query.has_conflicts_query import EnrichedDiffHasConflictQuery
from ..query.merge_tracking_id import EnrichedDiffMergedTrackingIdQuery
from ..query.roots_metadata import EnrichedDiffRootsMetadataQuery
from ..query.save import EnrichedDiffRootsUpsertQuery, EnrichedNodeBatchCreateQuery, EnrichedNodesLinkQuery
from ..query.time_range_query import EnrichedDiffTimeRangeQuery
from ..query.update_conflict_query import EnrichedDiffConflictUpdateQuery
from .deserializer import EnrichedDiffDeserializer

log = get_logger()


class DiffRepository:
    def __init__(self, db: InfrahubDatabase, deserializer: EnrichedDiffDeserializer, max_save_batch_size: int = 1000):
        self.db = db
        self.deserializer = deserializer
        self.max_save_batch_size = max_save_batch_size

    async def _run_get_diff_query(
        self,
        base_branch_name: str,
        diff_branch_names: list[str],
        batch_size_limit: int,
        limit: int | None = None,
        from_time: Timestamp | None = None,
        to_time: Timestamp | None = None,
        filters: EnrichedDiffQueryFilters | None = None,
        offset: int = 0,
        include_parents: bool = True,
        max_depth: int | None = None,
        tracking_id: TrackingId | None = None,
        diff_ids: list[str] | None = None,
    ) -> list[EnrichedDiffRoot]:
        self.deserializer.initialize()
        final_row_number = None
        if limit:
            final_row_number = offset + limit
        has_more_data = True
        while has_more_data and (final_row_number is None or offset < final_row_number):
            if final_row_number is not None and offset + batch_size_limit > final_row_number:
                batch_size_limit = final_row_number - offset
            get_query = await EnrichedDiffGetQuery.init(
                db=self.db,
                base_branch_name=base_branch_name,
                diff_branch_names=diff_branch_names,
                from_time=from_time,
                to_time=to_time,
                filters=filters,
                max_depth=max_depth,
                limit=batch_size_limit,
                offset=offset,
                tracking_id=tracking_id,
                diff_ids=diff_ids,
            )
            log.info(f"Beginning enriched diff get query {batch_size_limit=}, {offset=}")
            await get_query.execute(db=self.db)
            log.info("Enriched diff get query complete")
            last_result = None
            for query_result in get_query.get_results():
                await self.deserializer.read_result(result=query_result, include_parents=include_parents)
                last_result = query_result
            has_more_data = False
            if last_result:
                has_more_data = last_result.get_as_type("has_more_data", bool)
            offset += batch_size_limit
        return await self.deserializer.deserialize()

    async def get(
        self,
        base_branch_name: str,
        diff_branch_names: list[str],
        from_time: Timestamp | None = None,
        to_time: Timestamp | None = None,
        filters: EnrichedDiffQueryFilters | None = None,
        include_parents: bool = True,
        limit: int | None = None,
        offset: int | None = None,
        tracking_id: TrackingId | None = None,
        diff_ids: list[str] | None = None,
        include_empty: bool = False,
    ) -> list[EnrichedDiffRoot]:
        final_max_depth = config.SETTINGS.database.max_depth_search_hierarchy
        batch_size_limit = int(config.SETTINGS.database.query_size_limit / 10)
        diff_roots = await self._run_get_diff_query(
            base_branch_name=base_branch_name,
            diff_branch_names=diff_branch_names,
            batch_size_limit=batch_size_limit,
            limit=limit,
            from_time=from_time,
            to_time=to_time,
            filters=EnrichedDiffQueryFilters(**dict(filters or {})),
            include_parents=include_parents,
            max_depth=final_max_depth,
            offset=offset or 0,
            tracking_id=tracking_id,
            diff_ids=diff_ids,
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
        batch_size_limit = int(config.SETTINGS.database.query_size_limit / 10)
        diff_branch_roots = await self._run_get_diff_query(
            base_branch_name=base_branch_name,
            diff_branch_names=[diff_branch_name],
            from_time=from_time,
            to_time=to_time,
            max_depth=max_depth,
            batch_size_limit=batch_size_limit,
        )
        diffs_by_uuid = {dbr.uuid: dbr for dbr in diff_branch_roots}
        base_branch_roots = await self._run_get_diff_query(
            base_branch_name=base_branch_name,
            diff_branch_names=[base_branch_name],
            max_depth=max_depth,
            batch_size_limit=batch_size_limit,
            diff_ids=[d.partner_uuid for d in diffs_by_uuid.values() if d.partner_uuid],
        )
        diffs_by_uuid.update({bbr.uuid: bbr for bbr in base_branch_roots})
        diff_pairs = []
        for dbr in diff_branch_roots:
            if dbr.partner_uuid is None:
                continue
            base_branch_diff = diffs_by_uuid[dbr.partner_uuid]
            diff_pairs.append(
                EnrichedDiffs(
                    base_branch_name=base_branch_name,
                    diff_branch_name=diff_branch_name,
                    base_branch_diff=base_branch_diff,
                    diff_branch_diff=dbr,
                )
            )
        return diff_pairs

    async def hydrate_diff_pair(
        self,
        enriched_diffs_metadata: EnrichedDiffsMetadata,
        node_identifiers: Iterable[NodeIdentifier] | None = None,
    ) -> EnrichedDiffs:
        filters = EnrichedDiffQueryFilters()
        if node_identifiers:
            filters.identifiers = list(node_identifiers)
        hydrated_base_diff = await self.get_one(
            diff_branch_name=enriched_diffs_metadata.base_branch_name,
            diff_id=enriched_diffs_metadata.base_branch_diff.uuid,
            filters=filters,
        )
        hydrated_branch_diff = await self.get_one(
            diff_branch_name=enriched_diffs_metadata.diff_branch_name,
            diff_id=enriched_diffs_metadata.diff_branch_diff.uuid,
            filters=filters,
        )
        return EnrichedDiffs(
            base_branch_name=enriched_diffs_metadata.base_branch_name,
            diff_branch_name=enriched_diffs_metadata.diff_branch_name,
            base_branch_diff=hydrated_base_diff,
            diff_branch_diff=hydrated_branch_diff,
        )

    async def get_one(
        self,
        diff_branch_name: str,
        tracking_id: TrackingId | None = None,
        diff_id: str | None = None,
        filters: EnrichedDiffQueryFilters | None = None,
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
            size_count = 0
            for node in diff_root.nodes:
                node_size_count = node.num_properties
                if size_count + node_size_count < self.max_save_batch_size:
                    node_requests.append(EnrichedNodeCreateRequest(node=node, root_uuid=diff_root.uuid))
                    size_count += node_size_count
                else:
                    log.info(f"Num nodes in batch: {len(node_requests)}, num properties in batch: {size_count}")
                    yield node_requests
                    size_count = node_size_count
                    node_requests = [EnrichedNodeCreateRequest(node=node, root_uuid=diff_root.uuid)]
        if node_requests:
            log.info(f"Num nodes in batch: {len(node_requests)}, num properties in batch: {size_count}")
            yield node_requests

    @retry_db_transaction(name="enriched_diff_metadata_save")
    async def _save_root_metadata(self, enriched_diffs: EnrichedDiffsMetadata) -> None:
        log.info("Updating diff metadata...")
        root_query = await EnrichedDiffRootsUpsertQuery.init(db=self.db, enriched_diffs=enriched_diffs)
        await root_query.execute(db=self.db)
        log.info("Diff metadata updated.")

    async def _save_node_batch(self, node_create_batch: list[EnrichedNodeCreateRequest]) -> None:
        node_query = await EnrichedNodeBatchCreateQuery.init(db=self.db, node_create_batch=node_create_batch)
        try:
            await node_query.execute(db=self.db)
        except TransientError as exc:
            if not exc.code or "OutOfMemoryError".lower() not in str(exc.code).lower():
                raise
            log.exception("Database memory error during save. Trying smaller transactions")
            for node_request in node_create_batch:
                log.info(
                    f"Updating node {node_request.node.uuid}, num_properties={node_request.node.num_properties}..."
                )
                single_node_query = await EnrichedNodeBatchCreateQuery.init(
                    db=self.db, node_create_batch=[node_request]
                )
                await single_node_query.execute(db=self.db)

    async def _drop_nodes(self, diff_root: EnrichedDiffRoot, node_identifiers: list[NodeIdentifier]) -> None:
        drop_node_query = await EnrichedDiffDropNodesQuery.init(
            db=self.db, enriched_diff_uuid=diff_root.uuid, node_identifiers=node_identifiers
        )
        await drop_node_query.execute(db=self.db)

    @retry_db_transaction(name="enriched_diff_hierarchy_update")
    async def _run_hierarchy_links_update_query(self, diff_root_uuid: str, diff_nodes: list[EnrichedDiffNode]) -> None:
        log.info(f"Updating diff hierarchy links, num_nodes={len(diff_nodes)}")
        link_query = await EnrichedNodesLinkQuery.init(db=self.db, diff_root_uuid=diff_root_uuid, diff_nodes=diff_nodes)
        await link_query.execute(db=self.db)

    async def _update_hierarchy_links(self, enriched_diffs: EnrichedDiffs) -> None:
        for diff_root in (enriched_diffs.base_branch_diff, enriched_diffs.diff_branch_diff):
            nodes_to_update = []
            for node in diff_root.nodes:
                if any(r.nodes for r in node.relationships):
                    nodes_to_update.append(node)
                if len(nodes_to_update) >= config.SETTINGS.database.query_size_limit:
                    await self._run_hierarchy_links_update_query(
                        diff_root_uuid=diff_root.uuid, diff_nodes=nodes_to_update
                    )
                    nodes_to_update = []
            if nodes_to_update:
                await self._run_hierarchy_links_update_query(diff_root_uuid=diff_root.uuid, diff_nodes=nodes_to_update)

    async def _update_summary_counts(self, diff_root: EnrichedDiffRoot) -> None:
        max_nodes_limit = config.SETTINGS.database.query_size_limit
        num_nodes = len(diff_root.nodes)
        if diff_root.exists_on_database and num_nodes < max_nodes_limit:
            await self.add_summary_counts(
                diff_branch_name=diff_root.diff_branch_name,
                diff_id=diff_root.uuid,
                node_uuids=None,
            )
            return
        node_uuids: list[str] = []
        for diff_node in diff_root.nodes:
            node_uuids.append(diff_node.uuid)
            if len(node_uuids) >= max_nodes_limit:
                await self.add_summary_counts(
                    diff_branch_name=diff_root.diff_branch_name,
                    diff_id=diff_root.uuid,
                    node_uuids=node_uuids,
                )
                node_uuids = []
        if node_uuids:
            await self.add_summary_counts(
                diff_branch_name=diff_root.diff_branch_name,
                diff_id=diff_root.uuid,
                node_uuids=node_uuids,
            )

    async def save(
        self,
        enriched_diffs: EnrichedDiffs | EnrichedDiffsMetadata,
        do_summary_counts: bool = True,
        node_identifiers_to_drop: list[NodeIdentifier] | None = None,
    ) -> None:
        # metadata-only update
        if not isinstance(enriched_diffs, EnrichedDiffs):
            await self._save_root_metadata(enriched_diffs=enriched_diffs)
            return

        count_nodes_remaining = len(enriched_diffs.base_branch_diff.nodes) + len(enriched_diffs.diff_branch_diff.nodes)
        log.info(f"Saving diff (num_nodes={count_nodes_remaining})...")
        for batch_num, node_create_batch in enumerate(
            self._get_node_create_request_batch(enriched_diffs=enriched_diffs)
        ):
            log.info(f"Saving node batch #{batch_num}...")
            await self._save_node_batch(node_create_batch=node_create_batch)
            count_nodes_remaining -= len(node_create_batch)
            log.info(f"Batch saved. {count_nodes_remaining=}")
        if node_identifiers_to_drop:
            await self._drop_nodes(diff_root=enriched_diffs.diff_branch_diff, node_identifiers=node_identifiers_to_drop)
        await self._update_hierarchy_links(enriched_diffs=enriched_diffs)
        if do_summary_counts:
            await self._update_summary_counts(diff_root=enriched_diffs.diff_branch_diff)
        await self._save_root_metadata(enriched_diffs=enriched_diffs)

    async def summary(
        self,
        base_branch_name: str,
        diff_branch_names: list[str],
        from_time: Timestamp | None = None,
        to_time: Timestamp | None = None,
        tracking_id: TrackingId | None = None,
        filters: dict | None = None,
    ) -> DiffSummaryCounters | None:
        query = await DiffSummaryQuery.init(
            db=self.db,
            base_branch_name=base_branch_name,
            diff_branch_names=diff_branch_names,
            filters=EnrichedDiffQueryFilters(**dict(filters or {})),
            from_time=from_time,
            to_time=to_time,
            tracking_id=tracking_id,
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

    async def get_diff_pairs_metadata(
        self,
        diff_branch_names: list[str] | None = None,
        base_branch_names: list[str] | None = None,
        from_time: Timestamp | None = None,
        to_time: Timestamp | None = None,
        tracking_id: TrackingId | None = None,
    ) -> list[EnrichedDiffsMetadata]:
        if diff_branch_names and base_branch_names:
            diff_branch_names += base_branch_names
        empty_roots = await self.get_roots_metadata(
            diff_branch_names=diff_branch_names,
            base_branch_names=base_branch_names,
            from_time=from_time,
            to_time=to_time,
            tracking_id=tracking_id,
        )
        roots_by_id = {root.uuid: root for root in empty_roots}
        pairs: list[EnrichedDiffsMetadata] = []
        for branch_root in empty_roots:
            if branch_root.base_branch_name == branch_root.diff_branch_name or branch_root.partner_uuid is None:
                continue
            base_root = roots_by_id[branch_root.partner_uuid]
            pairs.append(
                EnrichedDiffsMetadata(
                    base_branch_name=branch_root.base_branch_name,
                    diff_branch_name=branch_root.diff_branch_name,
                    base_branch_diff=base_root,
                    diff_branch_diff=branch_root,
                )
            )
        return pairs

    async def get_roots_metadata(
        self,
        diff_branch_names: list[str] | None = None,
        base_branch_names: list[str] | None = None,
        from_time: Timestamp | None = None,
        to_time: Timestamp | None = None,
        tracking_id: TrackingId | None = None,
    ) -> list[EnrichedDiffRootMetadata]:
        query = await EnrichedDiffRootsMetadataQuery.init(
            db=self.db,
            diff_branch_names=diff_branch_names,
            base_branch_names=base_branch_names,
            from_time=from_time,
            to_time=to_time,
            tracking_id=tracking_id,
        )
        await query.execute(db=self.db)
        diff_roots = []
        for neo4j_node in query.get_root_nodes_metadata():
            diff_roots.append(self.deserializer.build_diff_root_metadata(root_node=neo4j_node))
        return diff_roots

    async def diff_has_conflicts(
        self,
        diff_branch_name: str,
        tracking_id: TrackingId | None = None,
        diff_id: str | None = None,
    ) -> bool:
        query = await EnrichedDiffHasConflictQuery.init(
            db=self.db, diff_branch_name=diff_branch_name, tracking_id=tracking_id, diff_id=diff_id
        )
        await query.execute(db=self.db)
        return await query.has_conflict()

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

    async def get_all_conflicts_for_diff(
        self,
        diff_branch_name: str,
        tracking_id: TrackingId | None = None,
        diff_id: str | None = None,
    ) -> AsyncGenerator[tuple[str, EnrichedDiffConflict], None]:
        query = await EnrichedDiffAllConflictsQuery.init(
            db=self.db, diff_branch_name=diff_branch_name, tracking_id=tracking_id, diff_id=diff_id
        )
        await query.execute(db=self.db)
        for conflict_path, conflict_node in query.get_conflict_paths_and_nodes():
            yield (conflict_path, self.deserializer.deserialize_conflict(diff_conflict_node=conflict_node))

    async def get_node_field_summaries(
        self, diff_branch_name: str, tracking_id: TrackingId | None = None, diff_id: str | None = None
    ) -> list[NodeDiffFieldSummary]:
        query = await EnrichedDiffNodeFieldSummaryQuery.init(
            db=self.db, diff_branch_name=diff_branch_name, tracking_id=tracking_id, diff_id=diff_id
        )
        await query.execute(db=self.db)
        return await query.get_field_summaries()

    async def mark_tracking_ids_merged(self, tracking_ids: list[TrackingId]) -> None:
        query = await EnrichedDiffMergedTrackingIdQuery.init(db=self.db, tracking_ids=tracking_ids)
        await query.execute(db=self.db)

    async def get_num_changes_in_time_range_by_branch(
        self, branch_names: list[str], from_time: Timestamp, to_time: Timestamp
    ) -> dict[str, int]:
        query = await DiffCountChanges.init(db=self.db, branch_names=branch_names, diff_from=from_time, diff_to=to_time)
        await query.execute(db=self.db)
        return query.get_num_changes_by_branch()

    async def get_node_field_specifiers(self, diff_id: str) -> NodeFieldSpecifierMap:
        limit = config.SETTINGS.database.query_size_limit
        offset = 0
        specifiers_map = NodeFieldSpecifierMap()
        while True:
            query = await EnrichedDiffFieldSpecifiersQuery.init(db=self.db, diff_id=diff_id, offset=offset, limit=limit)
            await query.execute(db=self.db)
            has_data = False
            for field_specifier_tuple in query.get_node_field_specifier_tuples():
                specifiers_map.add_entry(
                    node_uuid=field_specifier_tuple[0],
                    kind=field_specifier_tuple[1],
                    field_name=field_specifier_tuple[2],
                )
                has_data = True
            if not has_data:
                break
            offset += limit
        return specifiers_map

    async def add_summary_counts(
        self,
        diff_branch_name: str,
        tracking_id: TrackingId | None = None,
        diff_id: str | None = None,
        node_uuids: list[str] | None = None,
    ) -> None:
        await self._add_field_summary_counts(
            diff_branch_name=diff_branch_name,
            tracking_id=tracking_id,
            diff_id=diff_id,
            node_uuids=node_uuids,
        )
        await self._add_node_summary_counts(
            diff_branch_name=diff_branch_name,
            tracking_id=tracking_id,
            diff_id=diff_id,
            node_uuids=node_uuids,
        )

    @retry_db_transaction(name="enriched_diff_field_summary_counts")
    async def _add_field_summary_counts(
        self,
        diff_branch_name: str,
        tracking_id: TrackingId | None = None,
        diff_id: str | None = None,
        node_uuids: list[str] | None = None,
    ) -> None:
        log.info("Updating field summary counts...")
        query = await DiffFieldsSummaryCountsEnricherQuery.init(
            db=self.db,
            diff_branch_name=diff_branch_name,
            tracking_id=tracking_id,
            diff_id=diff_id,
            node_uuids=node_uuids,
        )
        await query.execute(db=self.db)
        log.info("Field summary counts updated.")

    @retry_db_transaction(name="enriched_diff_node_summary_counts")
    async def _add_node_summary_counts(
        self,
        diff_branch_name: str,
        tracking_id: TrackingId | None = None,
        diff_id: str | None = None,
        node_uuids: list[str] | None = None,
    ) -> None:
        log.info("Updating node summary counts...")
        query = await DiffNodesSummaryCountsEnricherQuery.init(
            db=self.db,
            diff_branch_name=diff_branch_name,
            tracking_id=tracking_id,
            diff_id=diff_id,
            node_uuids=node_uuids,
        )
        await query.execute(db=self.db)
        log.info("node summary counts updated.")
