from enum import Enum
from typing import TYPE_CHECKING

from infrahub.core.constants import BranchConflictKeep, InfrahubKind, ProposedChangeState
from infrahub.core.integrity.object_conflict.conflict_recorder import ObjectConflictValidatorRecorder
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase

from .conflicts_extractor import DiffConflictsExtractor
from .model.path import ConflictSelection, EnrichedDiffConflict, EnrichedDiffRoot

if TYPE_CHECKING:
    from infrahub.core.protocols import CoreProposedChange


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
        proposed_changes = await NodeManager.query(
            db=self.db,
            schema=InfrahubKind.PROPOSEDCHANGE,
            filters={"source_branch": enriched_diff.diff_branch_name, "state": ProposedChangeState.OPEN},
        )
        if not proposed_changes:
            return []
        proposed_change: CoreProposedChange = proposed_changes[0]
        enriched_conflicts = enriched_diff.get_all_conflicts()
        data_conflicts = await self.conflicts_extractor.get_data_conflicts(enriched_diff_root=enriched_diff)
        core_data_checks = await self.conflict_recorder.record_conflicts(
            proposed_change_id=proposed_change.get_id(), conflicts=data_conflicts
        )
        core_data_checks_by_id = {cdc.get_id(): cdc for cdc in core_data_checks}
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
        return core_data_checks

    def _get_keep_branch_for_enriched_conflict(
        self, enriched_conflict: EnrichedDiffConflict
    ) -> BranchConflictKeep | None:
        if enriched_conflict.selected_branch is ConflictSelection.BASE_BRANCH:
            return BranchConflictKeep.TARGET
        if enriched_conflict.selected_branch is ConflictSelection.DIFF_BRANCH:
            return BranchConflictKeep.SOURCE
        return None

    #     data_validator: CoreDataValidator | None = None
    #     validators = await proposed_change.validations.get_peers(db=self.db)
    #     for validator in validators.values():
    #         if validator.get_kind() == InfrahubKind.DATAVALIDATOR:
    #             data_validator = validator
    #             break
    #     if not data_validator:
    #         return
    #     data_checks = await data_validator.checks.get_peers(db=self.db)
    #     data_checks_by_id: dict[str, CoreDataCheck] = {c.get_id(): c for c in data_checks.values()}
    #     current_data_check_ids = set(data_checks_by_id.keys())
    #     enriched_conflicts = enriched_diff.get_all_conflicts()
    #     enriched_conflicts_by_id = {ec.uuid: ec for ec in enriched_conflicts}
    #     data_conflicts_by_conflict_id = await self.conflicts_extractor.get_data_conflicts(enriched_diff_root=enriched_diff)
    #     data_conflict_uuids = set(data_conflicts_by_conflict_id.keys())

    #     conflict_ids_to_keep = data_conflict_uuids & current_data_check_ids
    #     conflict_ids_to_add = data_conflict_uuids - current_data_check_ids
    #     conflict_ids_to_delete = current_data_check_ids - data_conflict_uuids

    #     for conflict_id in conflict_ids_to_delete:
    #         core_data_check = data_checks_by_id[conflict_id]
    #         await core_data_check.delete(db=self.db)

    #     for conflict_id in conflict_ids_to_keep:
    #         enriched_conflict = enriched_conflicts_by_id[conflict_id]
    #         core_data_check = data_checks_by_id[conflict_id]
    #         expected_keep_branch = self._get_keep_branch_for_enriched_conflict(enriched_conflict=enriched_conflict)
    #         expected_keep_branch_value = expected_keep_branch.value if isinstance(expected_keep_branch, Enum) else expected_keep_branch
    #         if core_data_check.keep_branch.value != expected_keep_branch_value:
    #             core_data_check.keep_branch.value = expected_keep_branch_value
    #             await core_data_check.save(db=self.db)

    #     for conflict_id in conflict_ids_to_add:
    #         data_conflict = data_conflicts_by_conflict_id[conflict_id]
    #         await self._add_core_data_check(data_conflict=data_conflict, conflict_id=conflict_id, validator=data_validator)

    # async def _add_core_data_check(self, data_conflict: DataConflict, conflict_id: str, validator: CoreDataValidator) -> CoreDataCheck:
    #     core_data_check = await Node.init(db=self.db, schema=InfrahubKind.DATACHECK)
    #     await core_data_check.new(
    #         db=self.db,
    #         id=conflict_id,
    #         label=data_conflict.label,
    #         origin="internal",
    #         kind="DataIntegrity",
    #         validator=validator.get_id(),
    #         conclusion="failure",
    #         severity="critical",
    #         conflicts=[data_conflict.to_conflict_dict()],
    #     )
    #     await core_data_check.save(db=self.db)
    #     return core_data_check
