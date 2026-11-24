from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, ValidatorConclusion
from infrahub.core.diff.model.diff import SchemaConflict
from infrahub.core.integrity.object_conflict.conflict_recorder import ObjectConflictValidatorRecorder
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreSchemaCheck, CoreSchemaValidator
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase


def _recorder(db: InfrahubDatabase) -> ObjectConflictValidatorRecorder:
    return ObjectConflictValidatorRecorder(
        db=db,
        validator_kind=InfrahubKind.SCHEMAVALIDATOR,
        validator_label="Schema Integrity",
        check_schema_kind=InfrahubKind.SCHEMACHECK,
    )


def _conflict() -> SchemaConflict:
    return SchemaConflict(
        name="schema/TestingSocket/voltage",
        type="node.attribute.add",
        kind="TestingSocket",
        id="socket-1",
        path="schema/TestingSocket/voltage",
        value="Node-level 'attribute' constraint violation on schema 'TestingSocket'.",
        branch="placeholder",
    )


async def _proposed_change(db: InfrahubDatabase, default_branch: Branch) -> str:
    proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE, branch=default_branch)
    await proposed_change.new(db=db, name="pc1", source_branch="branch2", destination_branch="main")
    await proposed_change.save(db=db)
    return proposed_change.id


async def _validator_conclusions(db: InfrahubDatabase) -> list[str]:
    validators = await NodeManager.query(db=db, schema=CoreSchemaValidator)
    return [validator.conclusion.value.value for validator in validators]


async def _check_results(db: InfrahubDatabase) -> list[tuple[str, int]]:
    checks = await NodeManager.query(db=db, schema=CoreSchemaCheck)
    return [(check.conclusion.value.value, len(check.conflicts.value)) for check in checks]


async def test_clear_failure_replaces_a_failure_recorded_before_the_timestamp_with_a_passing_result(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    proposed_change_id = await _proposed_change(db=db, default_branch=default_branch)
    await _recorder(db=db).record_conflicts(proposed_change_id=proposed_change_id, conflicts=[_conflict()])
    assert await _validator_conclusions(db=db) == [ValidatorConclusion.FAILURE.value]
    recorded_before = Timestamp()

    await _recorder(db=db).clear_failure(proposed_change_id=proposed_change_id, recorded_before=recorded_before)

    assert await _validator_conclusions(db=db) == [ValidatorConclusion.SUCCESS.value]
    assert await _check_results(db=db) == [(ValidatorConclusion.SUCCESS.value, 0)]


async def test_clear_failure_keeps_a_failure_recorded_after_the_timestamp(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    proposed_change_id = await _proposed_change(db=db, default_branch=default_branch)
    recorded_before = Timestamp()
    await _recorder(db=db).record_conflicts(proposed_change_id=proposed_change_id, conflicts=[_conflict()])
    validators = await NodeManager.query(db=db, schema=CoreSchemaValidator)
    completed_at = validators[0].completed_at.value
    assert Timestamp(completed_at) > recorded_before

    await _recorder(db=db).clear_failure(proposed_change_id=proposed_change_id, recorded_before=recorded_before)

    validators = await NodeManager.query(db=db, schema=CoreSchemaValidator)
    assert [(validator.conclusion.value.value, validator.completed_at.value) for validator in validators] == [
        (ValidatorConclusion.FAILURE.value, completed_at)
    ]
    assert await _check_results(db=db) == [(ValidatorConclusion.FAILURE.value, 1)]


async def test_clear_failure_leaves_a_passing_result_unchanged(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    proposed_change_id = await _proposed_change(db=db, default_branch=default_branch)
    await _recorder(db=db).record_conflicts(proposed_change_id=proposed_change_id, conflicts=[])
    validators = await NodeManager.query(db=db, schema=CoreSchemaValidator)
    completed_at = validators[0].completed_at.value
    checks_before = await NodeManager.query(db=db, schema=CoreSchemaCheck)

    await _recorder(db=db).clear_failure(proposed_change_id=proposed_change_id, recorded_before=Timestamp())

    validators = await NodeManager.query(db=db, schema=CoreSchemaValidator)
    assert [(validator.conclusion.value.value, validator.completed_at.value) for validator in validators] == [
        (ValidatorConclusion.SUCCESS.value, completed_at)
    ]
    checks_after = await NodeManager.query(db=db, schema=CoreSchemaCheck)
    assert [check.id for check in checks_after] == [check.id for check in checks_before]


async def test_clear_failure_creates_no_validator_when_none_was_recorded(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    proposed_change_id = await _proposed_change(db=db, default_branch=default_branch)

    await _recorder(db=db).clear_failure(proposed_change_id=proposed_change_id, recorded_before=Timestamp())

    assert await _validator_conclusions(db=db) == []
    assert await _check_results(db=db) == []
