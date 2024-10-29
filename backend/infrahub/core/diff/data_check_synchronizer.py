from enum import Enum

from infrahub.core.constants import BranchConflictKeep, InfrahubKind, ProposedChangeState
from infrahub.core.integrity.object_conflict.conflict_recorder import ObjectConflictValidatorRecorder
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import SchemaNotFoundError

from .conflicts_extractor import DiffConflictsExtractor
from .model.path import ConflictSelection, EnrichedDiffConflict, EnrichedDiffRoot


class DiffDataCheckSynchronizer:
    def __init__(
        self,
        db: InfrahubDatabase,
        conflicts_extractor: DiffConflictsExtractor,
        conflict_recorder: ObjectConflictValidatorRecorder,
    ):
        self.db = db
        self.conflicts_extractor = conflicts_extractor
        self.conflict_recorder = conflict_recorder

    async def synchronize(self, enriched_diff: EnrichedDiffRoot) -> list[Node]:
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
        enriched_conflicts = enriched_diff.get_all_conflicts()
        data_conflicts = await self.conflicts_extractor.get_data_conflicts(enriched_diff_root=enriched_diff)
        all_data_checks = []
        for pc in proposed_changes:
            core_data_checks = await self.conflict_recorder.record_conflicts(
                proposed_change_id=pc.get_id(), conflicts=data_conflicts
            )
            all_data_checks.extend(core_data_checks)
            core_data_checks_by_id = {cdc.enriched_conflict_id.value: cdc for cdc in core_data_checks}  # type: ignore[attr-defined]
            enriched_conflicts_by_id = {ec.uuid: ec for ec in enriched_conflicts}
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
