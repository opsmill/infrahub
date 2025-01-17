from typing import Sequence, cast

from infrahub.core.constants import InfrahubKind, ValidatorConclusion, ValidatorState
from infrahub.core.diff.model.diff import ObjectConflict
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreProposedChange
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import NodeNotFoundError


class ObjectConflictValidatorRecorder:
    def __init__(self, db: InfrahubDatabase, validator_kind: str, validator_label: str, check_schema_kind: str) -> None:
        self.db = db
        self.validator_kind = validator_kind
        self.validator_label = validator_label
        self.check_schema_kind = check_schema_kind

    async def record_conflicts(self, proposed_change_id: str, conflicts: Sequence[ObjectConflict]) -> list[Node]:
        try:
            proposed_change = await NodeManager.get_one_by_id_or_default_filter(
                id=proposed_change_id, kind=InfrahubKind.PROPOSEDCHANGE, db=self.db
            )
        except NodeNotFoundError:
            return []
        proposed_change = cast(CoreProposedChange, proposed_change)
        validator = await self.get_or_create_validator(proposed_change)
        await self.initialize_validator(validator)

        previous_checks = await validator.checks.get_peers(db=self.db)  # type: ignore[attr-defined]
        previous_checks_by_conflict_id = {check.enriched_conflict_id.value: check for check in previous_checks.values()}
        is_success = False

        current_checks: list[Node] = []
        check_ids_to_keep = set()
        if not conflicts:
            is_success = True
            check = None
            for previous_check in previous_checks.values():
                if previous_check.conflicts.value == []:  # type: ignore[attr-defined]
                    check = previous_check
                    check_ids_to_keep.add(check.id)

            if not check:
                check = await Node.init(db=self.db, schema=self.check_schema_kind)
                await check.new(
                    db=self.db,
                    label="Data Conflict",
                    origin="internal",
                    kind="DataIntegrity",
                    validator=validator.id,
                    conclusion="success",
                    severity="info",
                    conflicts=[],
                )
                await check.save(db=self.db)
            current_checks.append(check)

        for conflict in conflicts:
            conflicts_data = [conflict.to_conflict_dict()]
            conflict_obj = None
            if conflict.conflict_id and conflict.conflict_id in previous_checks_by_conflict_id:
                conflict_obj = previous_checks_by_conflict_id[conflict.conflict_id]
                check_ids_to_keep.add(conflict_obj.get_id())
            if not conflict_obj:
                for previous_check in previous_checks.values():
                    if previous_check.conflicts.value == conflicts_data:  # type: ignore[attr-defined]
                        conflict_obj = previous_check
                        check_ids_to_keep.add(conflict_obj.id)

            if not conflict_obj:
                conflict_obj = await Node.init(db=self.db, schema=self.check_schema_kind)

                await conflict_obj.new(
                    db=self.db,
                    enriched_conflict_id=conflict.conflict_id,
                    label=conflict.label,
                    origin="internal",
                    kind="DataIntegrity",
                    validator=validator.id,
                    conclusion="failure",
                    severity="critical",
                    conflicts=conflicts_data,
                )

                await conflict_obj.save(db=self.db)
            current_checks.append(conflict_obj)

        for check_id, previous_check in previous_checks.items():
            if check_id not in check_ids_to_keep:
                await previous_check.delete(db=self.db)

        await self.finalize_validator(validator, is_success)
        return current_checks

    async def get_validator(self, proposed_change: CoreProposedChange) -> Node | None:
        validations = await proposed_change.validations.get_peers(db=self.db, branch_agnostic=True)

        for validation in validations.values():
            if validation.get_kind() == self.validator_kind:
                return validation
        return None

    async def get_or_create_validator(self, proposed_change: CoreProposedChange) -> Node:
        validator_obj = await self.get_validator(proposed_change=proposed_change)
        if validator_obj:
            return validator_obj
        validator_obj = await Node.init(db=self.db, schema=self.validator_kind)
        await validator_obj.new(
            db=self.db,
            label=self.validator_label,
            state=ValidatorState.QUEUED.value,
            conclusion=ValidatorConclusion.UNKNOWN.value,
            proposed_change=proposed_change.id,
        )
        await validator_obj.save(db=self.db)
        return validator_obj

    async def initialize_validator(self, validator: Node) -> None:
        validator.state.value = ValidatorState.IN_PROGRESS.value  # type: ignore[attr-defined]
        validator.conclusion.value = ValidatorConclusion.UNKNOWN.value  # type: ignore[attr-defined]
        validator.started_at.value = Timestamp().to_string()  # type: ignore[attr-defined]
        validator.completed_at.value = ""  # type: ignore[attr-defined]
        await validator.save(db=self.db)

    async def finalize_validator(self, validator: Node, is_success: bool) -> None:
        validator.state.value = ValidatorState.COMPLETED.value  # type: ignore[attr-defined]
        validator.conclusion.value = (  # type: ignore[attr-defined]
            ValidatorConclusion.SUCCESS.value if is_success else ValidatorConclusion.FAILURE.value
        )
        validator.completed_at.value = Timestamp().to_string()  # type: ignore[attr-defined]
        await validator.save(db=self.db)
