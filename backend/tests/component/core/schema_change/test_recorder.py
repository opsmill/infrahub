from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import SYSTEM_USER_ID
from infrahub.core.schema_change.constants import SchemaChangeApplicationStatus, SchemaChangeStatus
from infrahub.core.schema_change.history_reader import SchemaChangeHistoryReader
from infrahub.core.schema_change.recorder import SchemaChangeRecorder, SchemaChangeRecording
from infrahub.core.schema_change.repository import SchemaChangeRepository
from infrahub.core.schema_change.version_resolver import SchemaChangeVersionResolver
from infrahub.core.timestamp import Timestamp
from tests.helpers.schema_change import (
    BranchHistorySeed,
    build_seeded_operations,
    seed_schema_change_history,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

EMPTY_OPERATIONS_ERROR = r"^A schema change needs at least one operation$"


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
