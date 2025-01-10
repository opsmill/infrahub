from enum import Enum

from infrahub.core.constants import BranchConflictKeep, InfrahubKind
from infrahub.core.integrity.object_conflict.conflict_recorder import ObjectConflictValidatorRecorder
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import SchemaNotFoundError
from infrahub.proposed_change.constants import ProposedChangeState

from .conflicts_extractor import DiffConflictsExtractor
from .model.diff import DataConflict
from .model.path import ConflictSelection, EnrichedDiffConflict, EnrichedDiffRoot, EnrichedDiffRootMetadata
from .repository.repository import DiffRepository


class DiffDataCheckSynchronizer:
    def __init__(
        self,
        db: InfrahubDatabase,
        conflicts_extractor: DiffConflictsExtractor,
        conflict_recorder: ObjectConflictValidatorRecorder,
        diff_repository: DiffRepository,
    ):
        self.db = db
        self.conflicts_extractor = conflicts_extractor
        self.conflict_recorder = conflict_recorder
        self.diff_repository = diff_repository
        self._enriched_conflicts_map: dict[str, EnrichedDiffConflict] | None = None
        self._data_conflicts: list[DataConflict] | None = None

    def _get_enriched_conflicts_map(self, enriched_diff: EnrichedDiffRoot) -> dict[str, EnrichedDiffConflict]:
        if self._enriched_conflicts_map is None:
            self._enriched_conflicts_map = enriched_diff.get_all_conflicts()
        return self._enriched_conflicts_map

    async def _get_data_conflicts(self, enriched_diff: EnrichedDiffRoot) -> list[DataConflict]:
        if self._data_conflicts is None:
            self._data_conflicts = await self.conflicts_extractor.get_data_conflicts(enriched_diff_root=enriched_diff)
        return self._data_conflicts

    async def synchronize(self, enriched_diff: EnrichedDiffRoot | EnrichedDiffRootMetadata) -> list[Node]:
        self._enriched_conflicts_map = None
        self._data_conflicts = None
        try:
            proposed_changes = await NodeManager.query(
                db=self.db,
                schema=InfrahubKind.PROPOSEDCHANGE,
                filters={"source_branch": enriched_diff.diff_branch_name, "state": ProposedChangeState.OPEN},
            )
        except SchemaNotFoundError:
            # if the CoreProposedChange schema does not exist, then there's nothing to do
            proposed_changes = []
        if not proposed_changes:
            return []
        all_data_checks = []
        for pc in proposed_changes:
            # if the enriched_diff is EnrichedDiffRootMetadata, then it has no new data in it
            if not isinstance(enriched_diff, EnrichedDiffRoot):
                has_validator = bool(await self.conflict_recorder.get_validator(proposed_change=pc))
                # if this pc does not have a validator, then it is a new ProposedChange
                if has_validator:
                    continue
                # if this is a new ProposedChange, we need to hydrate then EnrichedDiffRoot so that we can get the conflicts from it
                enriched_diff = await self.diff_repository.get_one(
                    diff_branch_name=enriched_diff.diff_branch_name, diff_id=enriched_diff.uuid
                )

            data_conflicts = await self._get_data_conflicts(enriched_diff=enriched_diff)
            enriched_conflicts_map = self._get_enriched_conflicts_map(enriched_diff=enriched_diff)
            core_data_checks = await self.conflict_recorder.record_conflicts(
                proposed_change_id=pc.get_id(), conflicts=data_conflicts
            )
            all_data_checks.extend(core_data_checks)
            core_data_checks_by_id = {cdc.enriched_conflict_id.value: cdc for cdc in core_data_checks}  # type: ignore[attr-defined]
            enriched_conflicts_by_id = {ec.uuid: ec for ec in enriched_conflicts_map.values()}
            for conflict_id, core_data_check in core_data_checks_by_id.items():
                enriched_conflict = enriched_conflicts_by_id.get(conflict_id)
                if not enriched_conflict:
                    continue
                expected_keep_branch = self._get_keep_branch_for_enriched_conflict(enriched_conflict=enriched_conflict)
                expected_keep_branch_value = (
                    expected_keep_branch.value if isinstance(expected_keep_branch, Enum) else expected_keep_branch
                )
                if core_data_check.keep_branch.value != expected_keep_branch_value:  # type: ignore[attr-defined]
                    core_data_check.keep_branch.value = expected_keep_branch_value  # type: ignore[attr-defined]
                    await core_data_check.save(db=self.db)
        return all_data_checks

    def _get_keep_branch_for_enriched_conflict(
        self, enriched_conflict: EnrichedDiffConflict
    ) -> BranchConflictKeep | None:
        if enriched_conflict.selected_branch is ConflictSelection.BASE_BRANCH:
            return BranchConflictKeep.TARGET
        if enriched_conflict.selected_branch is ConflictSelection.DIFF_BRANCH:
            return BranchConflictKeep.SOURCE
        return None
