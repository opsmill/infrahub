from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import SYSTEM_USER_ID
from infrahub.core.schema_change.constants import (
    SchemaChangeApplicationStatus,
    SchemaChangeMigrationStatus,
    SchemaChangeStatus,
)
from infrahub.core.schema_change.history_reader import SchemaChangeHistoryReader
from infrahub.core.schema_change.recorder import SchemaChangeRecorder, SchemaChangeRecording
from infrahub.core.schema_change.repository import SchemaChangeRepository
from infrahub.core.schema_change.version_resolver import SchemaChangeVersionResolver
from infrahub.core.timestamp import Timestamp
from tests.helpers.schema_change import (
    BranchHistorySeed,
    attribute_migration,
    build_seeded_operations,
    seed_schema_change_history,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

EMPTY_OPERATIONS_ERROR = r"^A schema change needs at least one operation$"
FAILURE_ERROR = "The migration attribute.kind.update failed on 3 nodes"


def _build_recorder(db: InfrahubDatabase, default_branch: Branch) -> SchemaChangeRecorder:
    repository = SchemaChangeRepository(db=db)
    return SchemaChangeRecorder(
        repository=repository,
        version_resolver=SchemaChangeVersionResolver(repository=repository, default_branch_name=default_branch.name),
    )


async def _read_records(
    db: InfrahubDatabase, branch: Branch
) -> list[tuple[str, SchemaChangeStatus, int | None, str | None, str | None, list[tuple[str, str, str]]]]:
    """Return each schema change of the branch with its version, parent, `applied_at` and applications."""
    reader = SchemaChangeHistoryReader(db=db)
    page = await reader.list_schema_changes(branch=branch.name, limit=10, offset=0)
    schema_change_ids = [str(entry.schema_change.uuid) for entry in page.entries]
    applications = await reader.list_applications(schema_change_ids=schema_change_ids)
    return [
        (
            schema_change_id,
            entry.schema_change.status,
            entry.schema_change.version,
            str(entry.parent.uuid) if entry.parent else None,
            entry.schema_change.applied_at,
            [
                (str(record.application.uuid), record.application.status.value, record.application.at)
                for record in applications[schema_change_id]
            ],
        )
        for schema_change_id, entry in zip(schema_change_ids, page.entries, strict=True)
    ]


async def test_start_creates_a_running_schema_change_without_version_and_a_running_application(
    db: InfrahubDatabase, default_branch: Branch
) -> None:
    recorder = _build_recorder(db=db, default_branch=default_branch)
    at = Timestamp()

    recording = await recorder.start(
        branch=default_branch, operations=build_seeded_operations(nbr_operations=2), at=at, user_id=SYSTEM_USER_ID
    )

    assert await _read_records(db=db, branch=default_branch) == [
        (
            recording.schema_change_id,
            SchemaChangeStatus.RUNNING,
            None,
            None,
            None,
            [(recording.application_id, SchemaChangeApplicationStatus.RUNNING.value, at.to_string())],
        )
    ]


async def test_complete_sets_both_to_applied_with_the_version_and_parent_from_the_resolver(
    db: InfrahubDatabase, default_branch: Branch
) -> None:
    history = await seed_schema_change_history(
        db=db, branches=[BranchHistorySeed(branch=default_branch.name, changes=[SchemaChangeStatus.APPLIED])]
    )
    seeded = history.schema_changes[0]
    recorder = _build_recorder(db=db, default_branch=default_branch)
    at = Timestamp()
    recording = await recorder.start(
        branch=default_branch, operations=build_seeded_operations(nbr_operations=1), at=at, user_id=SYSTEM_USER_ID
    )

    await recorder.complete(recording=recording, branch=default_branch, user_id=SYSTEM_USER_ID)

    records = await _read_records(db=db, branch=default_branch)
    assert records[1] == (
        recording.schema_change_id,
        SchemaChangeStatus.APPLIED,
        2,
        seeded.id,
        at.to_string(),
        [(recording.application_id, SchemaChangeApplicationStatus.APPLIED.value, at.to_string())],
    )
    assert len(records) == 2


async def test_two_changes_completed_in_turn_on_main_get_versions_1_and_2(
    db: InfrahubDatabase, default_branch: Branch
) -> None:
    recorder = _build_recorder(db=db, default_branch=default_branch)
    recordings: list[SchemaChangeRecording] = []

    for _ in range(2):
        recording = await recorder.start(
            branch=default_branch,
            operations=build_seeded_operations(nbr_operations=1),
            at=Timestamp(),
            user_id=SYSTEM_USER_ID,
        )
        await recorder.complete(recording=recording, branch=default_branch, user_id=SYSTEM_USER_ID)
        recordings.append(recording)

    first, second = recordings
    assert [
        (schema_change_id, status, version, parent_id)
        for schema_change_id, status, version, parent_id, _, _ in await _read_records(db=db, branch=default_branch)
    ] == [
        (first.schema_change_id, SchemaChangeStatus.APPLIED, 1, None),
        (second.schema_change_id, SchemaChangeStatus.APPLIED, 2, first.schema_change_id),
    ]


async def test_record_applied_creates_an_applied_schema_change_and_application_in_one_call(
    db: InfrahubDatabase, default_branch: Branch
) -> None:
    recorder = _build_recorder(db=db, default_branch=default_branch)
    at = Timestamp()

    recording = await recorder.record_applied(
        branch=default_branch, operations=build_seeded_operations(nbr_operations=1), at=at, user_id=SYSTEM_USER_ID
    )

    assert await _read_records(db=db, branch=default_branch) == [
        (
            recording.schema_change_id,
            SchemaChangeStatus.APPLIED,
            1,
            None,
            at.to_string(),
            [(recording.application_id, SchemaChangeApplicationStatus.APPLIED.value, at.to_string())],
        )
    ]


async def test_start_and_record_applied_refuse_an_empty_list_of_operations(
    db: InfrahubDatabase, default_branch: Branch
) -> None:
    recorder = _build_recorder(db=db, default_branch=default_branch)

    with pytest.raises(ValueError, match=EMPTY_OPERATIONS_ERROR):
        await recorder.start(branch=default_branch, operations=[], at=Timestamp(), user_id=SYSTEM_USER_ID)
    with pytest.raises(ValueError, match=EMPTY_OPERATIONS_ERROR):
        await recorder.record_applied(branch=default_branch, operations=[], at=Timestamp(), user_id=SYSTEM_USER_ID)

    assert await _read_records(db=db, branch=default_branch) == []


async def test_fail_sets_both_to_failed_with_the_error_and_without_version_or_parent(
    db: InfrahubDatabase, default_branch: Branch
) -> None:
    await seed_schema_change_history(
        db=db, branches=[BranchHistorySeed(branch=default_branch.name, changes=[SchemaChangeStatus.APPLIED])]
    )
    recorder = _build_recorder(db=db, default_branch=default_branch)
    at = Timestamp()
    recording = await recorder.start(
        branch=default_branch, operations=build_seeded_operations(nbr_operations=1), at=at, user_id=SYSTEM_USER_ID
    )

    await recorder.fail(recording=recording, error=FAILURE_ERROR, user_id=SYSTEM_USER_ID)

    records = await _read_records(db=db, branch=default_branch)
    assert records[1] == (
        recording.schema_change_id,
        SchemaChangeStatus.FAILED,
        None,
        None,
        None,
        [(recording.application_id, SchemaChangeApplicationStatus.FAILED.value, at.to_string())],
    )
    assert len(records) == 2
    applications = await SchemaChangeHistoryReader(db=db).list_applications(
        schema_change_ids=[recording.schema_change_id]
    )
    assert [record.application.error for record in applications[recording.schema_change_id]] == [FAILURE_ERROR]


async def test_fail_rolls_back_the_applied_migration_records_and_keeps_the_others(
    db: InfrahubDatabase, default_branch: Branch
) -> None:
    recorder = _build_recorder(db=db, default_branch=default_branch)
    recording = await recorder.start(
        branch=default_branch,
        operations=build_seeded_operations(nbr_operations=1),
        at=Timestamp(),
        user_id=SYSTEM_USER_ID,
    )
    repository = SchemaChangeRepository(db=db)
    statuses_before = [
        SchemaChangeMigrationStatus.APPLIED,
        SchemaChangeMigrationStatus.FAILED,
        SchemaChangeMigrationStatus.RUNNING,
        SchemaChangeMigrationStatus.WAITING,
    ]
    record_ids = await repository.create_migration_records(
        application_id=recording.application_id,
        migrations=[attribute_migration(field_name=f"field{position}") for position in range(len(statuses_before))],
    )
    for position, status in enumerate(statuses_before):
        if status != SchemaChangeMigrationStatus.WAITING:
            await repository.set_migration_records_status(
                record_ids=[record_ids[position]], status=status, nbr_migrations_executed=None, errors=[]
            )

    await recorder.fail(recording=recording, error=FAILURE_ERROR, user_id=SYSTEM_USER_ID)

    applications = await SchemaChangeHistoryReader(db=db).list_applications(
        schema_change_ids=[recording.schema_change_id]
    )
    [application] = applications[recording.schema_change_id]
    assert [(migration.position, migration.status) for migration in application.migrations] == [
        (0, SchemaChangeMigrationStatus.ROLLED_BACK),
        (1, SchemaChangeMigrationStatus.FAILED),
        (2, SchemaChangeMigrationStatus.RUNNING),
        (3, SchemaChangeMigrationStatus.WAITING),
    ]


async def test_change_completed_after_a_failed_one_gets_the_next_version_with_the_last_applied_as_parent(
    db: InfrahubDatabase, default_branch: Branch
) -> None:
    recorder = _build_recorder(db=db, default_branch=default_branch)
    applied = await recorder.record_applied(
        branch=default_branch,
        operations=build_seeded_operations(nbr_operations=1),
        at=Timestamp(),
        user_id=SYSTEM_USER_ID,
    )
    failed = await recorder.start(
        branch=default_branch,
        operations=build_seeded_operations(nbr_operations=1),
        at=Timestamp(),
        user_id=SYSTEM_USER_ID,
    )
    await recorder.fail(recording=failed, error=FAILURE_ERROR, user_id=SYSTEM_USER_ID)
    corrected = await recorder.start(
        branch=default_branch,
        operations=build_seeded_operations(nbr_operations=1),
        at=Timestamp(),
        user_id=SYSTEM_USER_ID,
    )

    await recorder.complete(recording=corrected, branch=default_branch, user_id=SYSTEM_USER_ID)

    assert [
        (schema_change_id, status, version, parent_id)
        for schema_change_id, status, version, parent_id, _, _ in await _read_records(db=db, branch=default_branch)
    ] == [
        (applied.schema_change_id, SchemaChangeStatus.APPLIED, 1, None),
        (corrected.schema_change_id, SchemaChangeStatus.APPLIED, 2, applied.schema_change_id),
        (failed.schema_change_id, SchemaChangeStatus.FAILED, None, None),
    ]
