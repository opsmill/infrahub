from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Iterable, Literal, Sequence, overload
from uuid import uuid4

from infrahub import lock
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import ValidationError
from infrahub.log import get_logger

from .model.path import (
    BranchTrackingId,
    EnrichedDiffRoot,
    EnrichedDiffRootMetadata,
    EnrichedDiffs,
    EnrichedDiffsMetadata,
    NameTrackingId,
    TrackingId,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node

    from .calculator import DiffCalculator
    from .combiner import DiffCombiner
    from .conflict_transferer import DiffConflictTransferer
    from .conflicts_enricher import ConflictsEnricher
    from .data_check_synchronizer import DiffDataCheckSynchronizer
    from .enricher.aggregated import AggregatedDiffEnricher
    from .enricher.labels import DiffLabelsEnricher
    from .repository.repository import DiffRepository


log = get_logger()


@dataclass
class EnrichedDiffRequest:
    base_branch: Branch
    diff_branch: Branch
    from_time: Timestamp
    to_time: Timestamp
    tracking_id: TrackingId
    node_field_specifiers: dict[str, set[str]] = field(default_factory=dict)

    def __repr__(self) -> str:
        return (
            f"EnrichedDiffRequest(base_branch_name={self.base_branch.name}, diff_branch_name={self.diff_branch.name},"
            f" from_time={self.from_time.to_string()}, to_time={self.to_time.to_string()},"
            f" tracking_id={self.tracking_id.serialize() if self.tracking_id else None}),"
            f" num_node_field_specifiers={len(self.node_field_specifiers)}"
        )


class DiffCoordinator:
    lock_namespace = "diff-update"

    def __init__(
        self,
        diff_repo: DiffRepository,
        diff_calculator: DiffCalculator,
        diff_enricher: AggregatedDiffEnricher,
        diff_combiner: DiffCombiner,
        conflicts_enricher: ConflictsEnricher,
        labels_enricher: DiffLabelsEnricher,
        data_check_synchronizer: DiffDataCheckSynchronizer,
        conflict_transferer: DiffConflictTransferer,
    ) -> None:
        self.diff_repo = diff_repo
        self.diff_calculator = diff_calculator
        self.diff_enricher = diff_enricher
        self.diff_combiner = diff_combiner
        self.conflicts_enricher = conflicts_enricher
        self.labels_enricher = labels_enricher
        self.data_check_synchronizer = data_check_synchronizer
        self.conflict_transferer = conflict_transferer
        self.lock_registry = lock.registry

    async def run_update(
        self,
        base_branch: Branch,
        diff_branch: Branch,
        from_time: str | None = None,
        to_time: str | None = None,
        name: str | None = None,
    ) -> None:
        # we are updating a diff that tracks the full lifetime of a branch
        if not name and not from_time and not to_time:
            await self.update_branch_diff(base_branch=base_branch, diff_branch=diff_branch)
            return

        if from_time:
            from_timestamp = Timestamp(from_time)
        else:
            from_timestamp = Timestamp(diff_branch.get_branched_from())
        if to_time:
            to_timestamp = Timestamp(to_time)
        else:
            to_timestamp = Timestamp()
        if not name:
            raise ValidationError("diff with specified time range requires a name")
        await self.create_or_update_arbitrary_timeframe_diff(
            base_branch=base_branch,
            diff_branch=diff_branch,
            from_time=from_timestamp,
            to_time=to_timestamp,
            name=name,
        )

    def _get_lock_name(self, base_branch_name: str, diff_branch_name: str, is_incremental: bool) -> str:
        lock_name = f"{base_branch_name}__{diff_branch_name}"
        if is_incremental:
            lock_name += "__incremental"
        return lock_name

    async def update_branch_diff(self, base_branch: Branch, diff_branch: Branch) -> EnrichedDiffRootMetadata:
        log.info(f"Received request to update branch diff for {base_branch.name} - {diff_branch.name}")
        incremental_lock_name = self._get_lock_name(
            base_branch_name=base_branch.name, diff_branch_name=diff_branch.name, is_incremental=True
        )
        existing_incremental_lock = self.lock_registry.get_existing(
            name=incremental_lock_name, namespace=self.lock_namespace
        )
        if existing_incremental_lock and await existing_incremental_lock.locked():
            log.info(f"Branch diff update for {base_branch.name} - {diff_branch.name} already in progress")
            async with self.lock_registry.get(name=incremental_lock_name, namespace=self.lock_namespace):
                log.info(f"Existing branch diff update for {base_branch.name} - {diff_branch.name} complete")
                return await self.diff_repo.get_one(
                    tracking_id=BranchTrackingId(name=diff_branch.name), diff_branch_name=diff_branch.name
                )
        general_lock_name = self._get_lock_name(
            base_branch_name=base_branch.name, diff_branch_name=diff_branch.name, is_incremental=False
        )
        from_time = Timestamp(diff_branch.get_branched_from())
        to_time = Timestamp()
        tracking_id = BranchTrackingId(name=diff_branch.name)
        async with (
            self.lock_registry.get(name=general_lock_name, namespace=self.lock_namespace),
            self.lock_registry.get(name=incremental_lock_name, namespace=self.lock_namespace),
        ):
            log.info(f"Acquired lock to run branch diff update for {base_branch.name} - {diff_branch.name}")
            enriched_diffs = await self._update_diffs(
                base_branch=base_branch,
                diff_branch=diff_branch,
                from_time=from_time,
                to_time=to_time,
                tracking_id=tracking_id,
                force_branch_refresh=False,
            )
            await self.diff_repo.save(enriched_diffs=enriched_diffs)
            await self._update_core_data_checks(enriched_diff=enriched_diffs.diff_branch_diff)
            log.info(f"Branch diff update complete for {base_branch.name} - {diff_branch.name}")
        return enriched_diffs.diff_branch_diff

    async def create_or_update_arbitrary_timeframe_diff(
        self,
        base_branch: Branch,
        diff_branch: Branch,
        from_time: Timestamp,
        to_time: Timestamp,
        name: str,
    ) -> EnrichedDiffRootMetadata:
        tracking_id = NameTrackingId(name=name)
        general_lock_name = self._get_lock_name(
            base_branch_name=base_branch.name, diff_branch_name=diff_branch.name, is_incremental=False
        )
        async with self.lock_registry.get(name=general_lock_name, namespace=self.lock_namespace):
            log.info(f"Acquired lock to run arbitrary diff update for {base_branch.name} - {diff_branch.name}")
            enriched_diffs = await self._update_diffs(
                base_branch=base_branch,
                diff_branch=diff_branch,
                from_time=from_time,
                to_time=to_time,
                tracking_id=tracking_id,
                force_branch_refresh=False,
            )

            await self.diff_repo.save(enriched_diffs=enriched_diffs)
            await self._update_core_data_checks(enriched_diff=enriched_diffs.diff_branch_diff)
            log.info(f"Arbitrary diff update complete for {base_branch.name} - {diff_branch.name}")
        return enriched_diffs.diff_branch_diff

    async def recalculate(
        self,
        base_branch: Branch,
        diff_branch: Branch,
        diff_id: str,
    ) -> EnrichedDiffRoot:
        general_lock_name = self._get_lock_name(
            base_branch_name=base_branch.name, diff_branch_name=diff_branch.name, is_incremental=False
        )
        async with self.lock_registry.get(name=general_lock_name, namespace=self.lock_namespace):
            log.info(f"Acquired lock to recalculate diff for {base_branch.name} - {diff_branch.name}")
            current_branch_diff = await self.diff_repo.get_one(diff_branch_name=diff_branch.name, diff_id=diff_id)
            current_base_diff = await self.diff_repo.get_one(
                diff_branch_name=base_branch.name, diff_id=current_branch_diff.partner_uuid
            )
            if current_branch_diff.tracking_id and isinstance(current_branch_diff.tracking_id, BranchTrackingId):
                to_time = Timestamp()
            else:
                to_time = current_branch_diff.to_time
            await self.diff_repo.delete_diff_roots(diff_root_uuids=[current_branch_diff.uuid, current_base_diff.uuid])
            from_time = current_branch_diff.from_time
            branched_from_time = Timestamp(diff_branch.get_branched_from())
            from_time = max(from_time, branched_from_time)
            enriched_diffs = await self._update_diffs(
                base_branch=base_branch,
                diff_branch=diff_branch,
                from_time=branched_from_time,
                to_time=to_time,
                tracking_id=current_branch_diff.tracking_id,
                force_branch_refresh=True,
            )
            if current_branch_diff:
                await self.conflict_transferer.transfer(
                    earlier=current_branch_diff, later=enriched_diffs.diff_branch_diff
                )

            await self.diff_repo.save(enriched_diffs=enriched_diffs)
            await self._update_core_data_checks(enriched_diff=enriched_diffs.diff_branch_diff)
            log.info(f"Diff recalculation complete for {base_branch.name} - {diff_branch.name}")
        return enriched_diffs.diff_branch_diff

    def _get_ordered_diff_pairs(
        self, diff_pairs: Iterable[EnrichedDiffsMetadata], allow_overlap: bool = False
    ) -> list[EnrichedDiffsMetadata]:
        ordered_diffs = sorted(diff_pairs, key=lambda d: d.diff_branch_diff.from_time)
        if allow_overlap:
            return ordered_diffs
        ordered_diffs_no_overlaps: list[EnrichedDiffsMetadata] = []
        for candidate_diff_pair in ordered_diffs:
            if not ordered_diffs_no_overlaps:
                ordered_diffs_no_overlaps.append(candidate_diff_pair)
                continue
            # no time overlap
            previous_diff = ordered_diffs_no_overlaps[-1].diff_branch_diff
            candidate_diff = candidate_diff_pair.diff_branch_diff
            if previous_diff.to_time <= candidate_diff.from_time:
                ordered_diffs_no_overlaps.append(candidate_diff_pair)
                continue
            previous_interval = previous_diff.time_range
            candidate_interval = candidate_diff.time_range
            # keep the diff that covers the larger time frame
            if candidate_interval > previous_interval:
                ordered_diffs_no_overlaps[-1] = candidate_diff_pair
        return ordered_diffs_no_overlaps

    def _build_enriched_diffs_with_no_nodes(self, diff_request: EnrichedDiffRequest) -> EnrichedDiffs:
        base_uuid = str(uuid4())
        branch_uuid = str(uuid4())
        return EnrichedDiffs(
            base_branch_name=diff_request.base_branch.name,
            diff_branch_name=diff_request.diff_branch.name,
            base_branch_diff=EnrichedDiffRoot(
                base_branch_name=diff_request.base_branch.name,
                diff_branch_name=diff_request.base_branch.name,
                from_time=diff_request.from_time,
                to_time=diff_request.to_time,
                tracking_id=diff_request.tracking_id,
                uuid=base_uuid,
                partner_uuid=branch_uuid,
            ),
            diff_branch_diff=EnrichedDiffRoot(
                base_branch_name=diff_request.base_branch.name,
                diff_branch_name=diff_request.diff_branch.name,
                from_time=diff_request.from_time,
                to_time=diff_request.to_time,
                tracking_id=diff_request.tracking_id,
                uuid=branch_uuid,
                partner_uuid=base_uuid,
            ),
        )

    @overload
    async def _update_diffs(
        self,
        base_branch: Branch,
        diff_branch: Branch,
        from_time: Timestamp,
        to_time: Timestamp,
        tracking_id: TrackingId,
        force_branch_refresh: Literal[True] = ...,
    ) -> EnrichedDiffs: ...

    @overload
    async def _update_diffs(
        self,
        base_branch: Branch,
        diff_branch: Branch,
        from_time: Timestamp,
        to_time: Timestamp,
        tracking_id: TrackingId,
        force_branch_refresh: Literal[False] = ...,
    ) -> EnrichedDiffs | EnrichedDiffsMetadata: ...

    async def _update_diffs(
        self,
        base_branch: Branch,
        diff_branch: Branch,
        from_time: Timestamp,
        to_time: Timestamp,
        tracking_id: TrackingId,
        force_branch_refresh: bool = False,
    ) -> EnrichedDiffs | EnrichedDiffsMetadata:
        # start with empty diffs b/c we only care about their metadata for now, hydrate them with data as needed
        diff_pairs_metadata = await self.diff_repo.get_diff_pairs_metadata(
            base_branch_names=[base_branch.name],
            diff_branch_names=[diff_branch.name],
            from_time=from_time,
            to_time=to_time,
            tracking_id=tracking_id,
        )
        aggregated_enriched_diffs = await self._aggregate_enriched_diffs(
            diff_request=EnrichedDiffRequest(
                base_branch=base_branch,
                diff_branch=diff_branch,
                from_time=from_time,
                to_time=to_time,
                tracking_id=tracking_id,
            ),
            partial_enriched_diffs=diff_pairs_metadata if not force_branch_refresh else None,
        )
        diff_uuids_to_delete: list[str] = []
        for diff_pair in diff_pairs_metadata:
            if (
                diff_pair.base_branch_diff.tracking_id == tracking_id
                and diff_pair.base_branch_diff.uuid != aggregated_enriched_diffs.base_branch_diff.uuid
                and diff_pair.base_branch_diff.exists_on_database
            ):
                diff_uuids_to_delete.append(diff_pair.base_branch_diff.uuid)
            if (
                diff_pair.diff_branch_diff.tracking_id == tracking_id
                and diff_pair.diff_branch_diff.uuid != aggregated_enriched_diffs.diff_branch_diff.uuid
                and diff_pair.diff_branch_diff.exists_on_database
            ):
                diff_uuids_to_delete.append(diff_pair.diff_branch_diff.uuid)

        if diff_uuids_to_delete:
            await self.diff_repo.delete_diff_roots(diff_root_uuids=diff_uuids_to_delete)

        # this is an EnrichedDiffsMetadata, so there are no nodes to enrich
        if not isinstance(aggregated_enriched_diffs, EnrichedDiffs):
            aggregated_enriched_diffs.update_metadata(from_time=from_time, to_time=to_time, tracking_id=tracking_id)
            return aggregated_enriched_diffs

        await self.conflicts_enricher.add_conflicts_to_branch_diff(
            base_diff_root=aggregated_enriched_diffs.base_branch_diff,
            branch_diff_root=aggregated_enriched_diffs.diff_branch_diff,
        )
        await self.labels_enricher.enrich(
            enriched_diff_root=aggregated_enriched_diffs.diff_branch_diff, conflicts_only=True
        )

        return aggregated_enriched_diffs

    @overload
    async def _aggregate_enriched_diffs(
        self,
        diff_request: EnrichedDiffRequest,
        partial_enriched_diffs: list[EnrichedDiffsMetadata],
    ) -> EnrichedDiffs | EnrichedDiffsMetadata: ...

    @overload
    async def _aggregate_enriched_diffs(
        self,
        diff_request: EnrichedDiffRequest,
        partial_enriched_diffs: None,
    ) -> EnrichedDiffs: ...

    async def _aggregate_enriched_diffs(
        self,
        diff_request: EnrichedDiffRequest,
        partial_enriched_diffs: list[EnrichedDiffsMetadata] | None,
    ) -> EnrichedDiffs | EnrichedDiffsMetadata:
        """
        If return is an EnrichedDiffsMetadata, it acts as a pointer to a diff in the database that has all the
            necessary data for this diff_request. Might have a different time range and/or tracking_id
        """
        aggregated_enriched_diffs: EnrichedDiffs | EnrichedDiffsMetadata | None = None
        if not partial_enriched_diffs:
            # no existing diffs to use in calculating this diff, so calculate the whole thing and return it
            aggregated_enriched_diffs = await self._calculate_enriched_diff(
                diff_request=diff_request, is_incremental_diff=False
            )

        if partial_enriched_diffs is not None and not aggregated_enriched_diffs:
            ordered_diffs = self._get_ordered_diff_pairs(diff_pairs=partial_enriched_diffs, allow_overlap=False)
            ordered_diff_reprs = [repr(d) for d in ordered_diffs]
            log.info(f"Ordered diffs for aggregation: {ordered_diff_reprs}")
            incremental_diffs_and_requests: list[EnrichedDiffsMetadata | EnrichedDiffRequest | None] = []
            current_time = diff_request.from_time
            while current_time < diff_request.to_time:
                # the next diff to include has already been calculated
                if ordered_diffs and ordered_diffs[0].diff_branch_diff.from_time == current_time:
                    current_diff = ordered_diffs.pop(0)
                    incremental_diffs_and_requests.append(current_diff)
                    current_time = current_diff.diff_branch_diff.to_time
                    continue
                # set the end time to the start of the next calculated diff or the end of the time range
                if ordered_diffs:
                    end_time = ordered_diffs[0].diff_branch_diff.from_time
                else:
                    end_time = diff_request.to_time
                # if there are no changes on either branch in this time range, then there cannot be a diff
                log.info(
                    f"Checking number of changes on branches for {diff_request!r}, from_time={current_time}, to_time={end_time}"
                )
                num_changes_by_branch = await self.diff_repo.get_num_changes_in_time_range_by_branch(
                    branch_names=[diff_request.base_branch.name, diff_request.diff_branch.name],
                    from_time=current_time,
                    to_time=end_time,
                )
                log.info(f"Number of changes: {num_changes_by_branch}")
                might_have_changes_in_time_range = any(num_changes_by_branch.values())
                if not might_have_changes_in_time_range:
                    incremental_diffs_and_requests.append(None)
                    current_time = end_time
                    continue

                incremental_diffs_and_requests.append(
                    EnrichedDiffRequest(
                        base_branch=diff_request.base_branch,
                        diff_branch=diff_request.diff_branch,
                        from_time=current_time,
                        to_time=end_time,
                        tracking_id=diff_request.tracking_id,
                    )
                )
                current_time = end_time

            aggregated_enriched_diffs = await self._concatenate_diffs_and_requests(
                diff_or_request_list=incremental_diffs_and_requests, full_diff_request=diff_request
            )

        # no changes during this time period, so generate an EnrichedDiffs with no nodes
        if not aggregated_enriched_diffs:
            return self._build_enriched_diffs_with_no_nodes(diff_request=diff_request)

        # metadata-only diff, means that a diff exists in the database that covers at least
        # part of this time period, but it might need to have its start or end time extended
        # to cover time ranges with no changes
        if not isinstance(aggregated_enriched_diffs, EnrichedDiffs):
            return aggregated_enriched_diffs

        # a new diff (with nodes) covering the time period
        aggregated_enriched_diffs.update_metadata(
            from_time=diff_request.from_time, to_time=diff_request.to_time, tracking_id=diff_request.tracking_id
        )
        return aggregated_enriched_diffs

    async def _concatenate_diffs_and_requests(
        self,
        diff_or_request_list: Sequence[EnrichedDiffsMetadata | EnrichedDiffRequest | None],
        full_diff_request: EnrichedDiffRequest,
    ) -> EnrichedDiffs | EnrichedDiffsMetadata | None:
        """
        Returns None if diff_or_request_list is empty or all Nones
            meaning there are no changes for the diff during this time period
        Returns EnrichedDiffsMetadata if diff_or_request_list includes one EnrichedDiffsMetadata and no EnrichedDiffRequests
            meaning no diffs needed to be hydrated and combined
        Otherwise, returns EnrichedDiffs
            meaning multiple diffs (some that may have been freshly calculated) were combined
        """
        previous_diff_pair: EnrichedDiffs | EnrichedDiffsMetadata | None = None
        updated_node_uuids: set[str] = set()
        for diff_or_request in diff_or_request_list:
            if isinstance(diff_or_request, EnrichedDiffRequest):
                if previous_diff_pair:
                    log.info(f"Getting node field specifiers diff uuid={previous_diff_pair.diff_branch_diff.uuid}")
                    node_field_specifiers = await self.diff_repo.get_node_field_specifiers(
                        diff_id=previous_diff_pair.diff_branch_diff.uuid,
                    )
                    log.info(f"Number node field specifiers: {len(node_field_specifiers)}")
                    diff_or_request.node_field_specifiers = node_field_specifiers
                is_incremental_diff = diff_or_request.from_time != full_diff_request.from_time
                calculated_diff = await self._calculate_enriched_diff(
                    diff_request=diff_or_request, is_incremental_diff=is_incremental_diff
                )
                updated_node_uuids |= calculated_diff.base_node_uuids
                updated_node_uuids |= calculated_diff.branch_node_uuids
                single_enriched_diffs: EnrichedDiffs | EnrichedDiffsMetadata = calculated_diff

            elif isinstance(diff_or_request, EnrichedDiffsMetadata):
                single_enriched_diffs = diff_or_request
            else:
                continue

            if previous_diff_pair is None:
                previous_diff_pair = single_enriched_diffs
                continue

            log.info("Combining diffs...")
            previous_diff_pair = await self._combine_diffs(
                earlier=previous_diff_pair,
                later=single_enriched_diffs,
                node_uuids=updated_node_uuids,
            )
            log.info("Diffs combined.")

        return previous_diff_pair

    async def _combine_diffs(
        self,
        earlier: EnrichedDiffs | EnrichedDiffsMetadata,
        later: EnrichedDiffs | EnrichedDiffsMetadata,
        node_uuids: set[str],
    ) -> EnrichedDiffs | EnrichedDiffsMetadata:
        log.info(f"Earlier diff to combine: {earlier!r}")
        log.info(f"Later diff to combine: {later!r}")
        # if one of the diffs is hydrated and has no data, we can combine them without hydrating the other
        if isinstance(earlier, EnrichedDiffs) and earlier.is_empty:
            later.base_branch_diff.from_time = earlier.base_branch_diff.from_time
            later.diff_branch_diff.from_time = earlier.diff_branch_diff.from_time
            return later
        if isinstance(later, EnrichedDiffs) and later.is_empty:
            earlier.base_branch_diff.to_time = later.base_branch_diff.to_time
            earlier.diff_branch_diff.to_time = later.diff_branch_diff.to_time
            return earlier

        # hydrate the diffs to combine, if necessary
        if not isinstance(earlier, EnrichedDiffs):
            log.info("Hydrating earlier diff...")
            earlier = await self.diff_repo.hydrate_diff_pair(enriched_diffs_metadata=earlier, node_uuids=node_uuids)
            log.info("Earlier diff hydrated.")
        if not isinstance(later, EnrichedDiffs):
            log.info("Hydrating later diff...")
            later = await self.diff_repo.hydrate_diff_pair(enriched_diffs_metadata=later, node_uuids=node_uuids)
            log.info("Later diff hydrated.")

        return await self.diff_combiner.combine(earlier_diffs=earlier, later_diffs=later)

    async def _update_core_data_checks(self, enriched_diff: EnrichedDiffRoot | EnrichedDiffRootMetadata) -> list[Node]:
        return await self.data_check_synchronizer.synchronize(enriched_diff=enriched_diff)

    async def _calculate_enriched_diff(
        self, diff_request: EnrichedDiffRequest, is_incremental_diff: bool
    ) -> EnrichedDiffs:
        log.info(f"Calculating diff for {diff_request!r}, include_unchanged={is_incremental_diff}")
        calculated_diff_pair = await self.diff_calculator.calculate_diff(
            base_branch=diff_request.base_branch,
            diff_branch=diff_request.diff_branch,
            from_time=diff_request.from_time,
            to_time=diff_request.to_time,
            include_unchanged=is_incremental_diff,
            previous_node_specifiers=diff_request.node_field_specifiers,
        )
        log.info("Calculation complete. Enriching diff...")
        enriched_diff_pair = await self.diff_enricher.enrich(
            calculated_diffs=calculated_diff_pair, tracking_id=diff_request.tracking_id
        )
        log.info("Enrichment complete")
        return enriched_diff_pair
