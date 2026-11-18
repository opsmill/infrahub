from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import SYSTEM_USER_ID
from infrahub.core.schema_change.recorder import SchemaChangeRecorder, SchemaChangeRecording
from infrahub.core.schema_change.repository import AppliedSchemaChangeVersion, CreatedSchemaChange
from infrahub.core.schema_change.version_resolver import SchemaChangeVersionResolver
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import DatabaseError
from tests.helpers.schema_change import build_seeded_operations
from tests.unit.core.schema_change.helpers import (
    CREATE_SCHEMA_CHANGE,
    FAILING_STORE_ERROR,
    GET_HIGHEST_APPLIED_VERSION,
    MARK_APPLIED,
    MARK_FAILED,
    FailingSchemaChangeRepository,
    RecordingSchemaChangeRepository,
    SchemaChangeRepositoryCall,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

MAIN = "main"
SCHEMA_CHANGE_ID = "3a7c1e94-2b6d-4f08-9e15-c4d8a2f6b031"
APPLICATION_ID = "9d2f6b18-4e3a-4c71-8b05-e7a1c3d5f924"
PARENT_ID = "51e8c3a7-6d2f-4b94-a0c1-8f3e7b2d9a56"
FAILURE_ERROR = "The migration attribute.kind.update failed on 3 nodes"
EMPTY_OPERATIONS_ERROR = r"^A schema change needs at least one operation$"
AT = Timestamp("2026-03-02T10:15:00Z")

CREATED = CreatedSchemaChange(schema_change_id=SCHEMA_CHANGE_ID, application_id=APPLICATION_ID)
RECORDING = SchemaChangeRecording(schema_change_id=SCHEMA_CHANGE_ID, application_id=APPLICATION_ID, at=AT)


def _build_recorder(repository: RecordingSchemaChangeRepository) -> SchemaChangeRecorder:
    return SchemaChangeRecorder(
        repository=repository,
        version_resolver=SchemaChangeVersionResolver(repository=repository, default_branch_name=MAIN),
    )


def _mark_applied_call(version: int, parent_id: str | None) -> SchemaChangeRepositoryCall:
    return SchemaChangeRepositoryCall(
        method=MARK_APPLIED,
        arguments={
            "schema_change_id": SCHEMA_CHANGE_ID,
            "application_id": APPLICATION_ID,
            "version": version,
            "parent_id": parent_id,
            "applied_at": AT,
            "user_id": SYSTEM_USER_ID,
        },
    )


async def test_start_creates_the_schema_change_and_returns_its_ids_with_the_time_of_the_application() -> None:
    repository = RecordingSchemaChangeRepository(created=[CREATED])
    operations = build_seeded_operations(nbr_operations=2)

    recording = await _build_recorder(repository=repository).start(
        branch=Branch(name=MAIN), operations=operations, at=AT, user_id=SYSTEM_USER_ID
    )

    assert recording == RECORDING
    assert repository.calls == [
        SchemaChangeRepositoryCall(
            method=CREATE_SCHEMA_CHANGE,
            arguments={"branch": MAIN, "operations": operations, "at": AT, "user_id": SYSTEM_USER_ID},
        )
    ]


async def test_complete_marks_the_schema_change_applied_with_the_next_version_of_the_branch_and_its_parent() -> None:
    repository = RecordingSchemaChangeRepository(
        highest_versions={MAIN: AppliedSchemaChangeVersion(schema_change_id=PARENT_ID, version=4)}
    )

    await _build_recorder(repository=repository).complete(
        recording=RECORDING, branch=Branch(name=MAIN), user_id=SYSTEM_USER_ID
    )

    assert repository.calls == [
        SchemaChangeRepositoryCall(method=GET_HIGHEST_APPLIED_VERSION, arguments={"branch": MAIN}),
        _mark_applied_call(version=5, parent_id=PARENT_ID),
    ]


async def test_record_applied_creates_the_schema_change_then_marks_it_applied() -> None:
    repository = RecordingSchemaChangeRepository(created=[CREATED])
    operations = build_seeded_operations(nbr_operations=1)

    recording = await _build_recorder(repository=repository).record_applied(
        branch=Branch(name=MAIN), operations=operations, at=AT, user_id=SYSTEM_USER_ID
    )

    assert recording == RECORDING
    assert repository.calls == [
        SchemaChangeRepositoryCall(
            method=CREATE_SCHEMA_CHANGE,
            arguments={"branch": MAIN, "operations": operations, "at": AT, "user_id": SYSTEM_USER_ID},
        ),
        SchemaChangeRepositoryCall(method=GET_HIGHEST_APPLIED_VERSION, arguments={"branch": MAIN}),
        _mark_applied_call(version=1, parent_id=None),
    ]


async def test_start_and_record_applied_refuse_an_empty_list_of_operations_and_store_nothing() -> None:
    repository = RecordingSchemaChangeRepository(created=[CREATED])
    recorder = _build_recorder(repository=repository)

    with pytest.raises(ValueError, match=EMPTY_OPERATIONS_ERROR):
        await recorder.start(branch=Branch(name=MAIN), operations=[], at=AT, user_id=SYSTEM_USER_ID)
    with pytest.raises(ValueError, match=EMPTY_OPERATIONS_ERROR):
        await recorder.record_applied(branch=Branch(name=MAIN), operations=[], at=AT, user_id=SYSTEM_USER_ID)

    assert repository.calls == []


async def test_fail_marks_the_schema_change_failed_with_the_error() -> None:
    repository = RecordingSchemaChangeRepository()

    await _build_recorder(repository=repository).fail(recording=RECORDING, error=FAILURE_ERROR, user_id=SYSTEM_USER_ID)

    assert repository.calls == [
        SchemaChangeRepositoryCall(
            method=MARK_FAILED,
            arguments={
                "schema_change_id": SCHEMA_CHANGE_ID,
                "application_id": APPLICATION_ID,
                "error": FAILURE_ERROR,
                "user_id": SYSTEM_USER_ID,
            },
        )
    ]


@dataclass(frozen=True)
class FailedWriteCase:
    name: str
    write: Callable[[SchemaChangeRecorder], Awaitable[None]]
    expected_methods: list[str]


FAILED_WRITE_CASES = [
    FailedWriteCase(
        name="complete",
        write=lambda recorder: recorder.complete(recording=RECORDING, branch=Branch(name=MAIN), user_id=SYSTEM_USER_ID),
        expected_methods=[GET_HIGHEST_APPLIED_VERSION, MARK_APPLIED],
    ),
    FailedWriteCase(
        name="fail",
        write=lambda recorder: recorder.fail(recording=RECORDING, error=FAILURE_ERROR, user_id=SYSTEM_USER_ID),
        expected_methods=[MARK_FAILED],
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in FAILED_WRITE_CASES])
async def test_a_status_write_that_fails_raises_its_error(test_case: FailedWriteCase) -> None:
    repository = FailingSchemaChangeRepository()

    with pytest.raises(DatabaseError, match=rf"^{FAILING_STORE_ERROR}$"):
        await test_case.write(_build_recorder(repository=repository))

    assert [call.method for call in repository.calls] == test_case.expected_methods
