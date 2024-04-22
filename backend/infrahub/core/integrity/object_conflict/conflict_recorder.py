from typing import List

import infrahub.core.constants.infrahubkind as InfrahubKind
from infrahub.core.constants import ValidatorConclusion, ValidatorState
from infrahub.core.diff.model import ObjectConflict
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase


class ObjectConflictValidatorRecorder:
    def __init__(self, db: InfrahubDatabase, validator_kind: str, validator_label: str, check_schema_kind: str) -> None:
        self.db = db
        self.validator_kind = validator_kind
        self.validator_label = validator_label
        self.check_schema_kind = check_schema_kind

    async def record_conflicts(self, proposed_change_id: str, conflicts: List[ObjectConflict]) -> None:
        proposed_change = await NodeManager.get_one_by_id_or_default_filter(
            id=proposed_change_id, schema_name=InfrahubKind.PROPOSEDCHANGE, db=self.db
        )
        validator = await self.get_or_create_validator(proposed_change)
        await self.initialize_validator(validator)

        previous_checks = await validator.checks.get_peers(db=self.db)  # type: ignore[attr-defined]
        is_success = False

        check_ids: List[str] = []
        keep_check = []
        if not conflicts:
            is_success = True
            check = None
            for previous_check in previous_checks.values():
                if previous_check.conflicts.value == []:
                    check = previous_check
                    keep_check.append(check.id)

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
            check_ids.append(check.id)

        for conflict in conflicts:
            conflicts_data = [conflict.to_conflict_dict()]
            conflict_obj = None
            for previous_check in previous_checks.values():
                if previous_check.conflicts.value == conflicts_data:
                    conflict_obj = previous_check
                    keep_check.append(conflict_obj.id)

            if not conflict_obj:
                conflict_obj = await Node.init(db=self.db, schema=self.check_schema_kind)

                await conflict_obj.new(
                    db=self.db,
                    label=f"{conflict.name} ({conflict.id})",
                    origin="internal",
                    kind="DataIntegrity",
                    validator=validator.id,
                    conclusion="failure",
                    severity="critical",
                    conflicts=conflicts_data,
                )

                await conflict_obj.save(db=self.db)
            check_ids.append(conflict_obj.id)

        for check_id, previous_check in previous_checks.items():
            if check_id not in keep_check:
                await previous_check.delete(db=self.db)

        await self.finalize_validator(validator, is_success, check_ids)

    async def get_or_create_validator(self, proposed_change: Node) -> Node:
        validations = await proposed_change.validations.get_peers(db=self.db)  # type: ignore[attr-defined]

        for validation in validations.values():
            if validation._schema.kind == self.validator_kind:
                return validation

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

    async def finalize_validator(self, validator: Node, is_success: bool, check_ids: List[str]) -> None:
        validator.state.value = ValidatorState.COMPLETED.value  # type: ignore[attr-defined]
        validator.conclusion.value = (  # type: ignore[attr-defined]
            ValidatorConclusion.SUCCESS.value if is_success else ValidatorConclusion.FAILURE.value
        )
        validator.checks.update = check_ids  # type: ignore[attr-defined]
        validator.completed_at.value = Timestamp().to_string()  # type: ignore[attr-defined]
        await validator.save(db=self.db)
