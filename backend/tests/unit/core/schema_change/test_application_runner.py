from __future__ import annotations

import logging
from dataclasses import dataclass, replace

import pytest

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.branch import Branch
from infrahub.core.constants import SchemaPathType
from infrahub.core.models import HashableModelDiff, SchemaDiff, SchemaUpdateMigrationInfo, SchemaUpdateValidationResult
from infrahub.core.path import SchemaPath
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.schema_change.application_runner import SchemaChangeApplicationRunner
from infrahub.core.schema_change.candidate import SchemaCandidate
from infrahub.core.schema_change.enums import SchemaOperationSection, SchemaOperationType
from infrahub.core.schema_change.operations import SchemaOperation
from infrahub.core.schema_change.recorder import SchemaChangeRecording
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import MigrationError
from tests.helpers.log import find_logged_events
from tests.unit.core.schema_change.helpers import (
    EXECUTOR_EXECUTE,
    RECORDED_APPLICATION_ID,
    RECORDED_SCHEMA_CHANGE_ID,
    RECORDER_COMPLETE,
    RECORDER_FAIL,
    RECORDER_START,
    FailingApplicationRecorder,
    FailingCompleteApplicationRecorder,
    FailingSchemaUpdateExecutor,
    RecordingApplicationRecorder,
    RecordingSchemaUpdateExecutor,
    SchemaApplicationCall,
)

USER_ID = "4d0c7e2a-6b19-4f3e-8a52-c1d9e7f30b64"
UPDATED_HASH = "f3a1c92e7b4d5068"
RECORD_FAILURE_EVENT = "Could not record the failure of a schema change"
RECORD_COMPLETION_EVENT = "Could not record the application of a schema change"
NO_OPERATION_EVENT = "Applying a schema change that has no operation, without recording it"
CHANGED_KIND = "TestCar"
MIGRATION_FAILURE = "The migration node.attribute.add failed on 2 nodes"


@dataclass(frozen=True)
class RunInput:
    branch: Branch
    origin_schema: SchemaBranch
    candidate: SchemaCandidate
    at: Timestamp
    context: InfrahubContext


def _build_run_input() -> RunInput:
    operation = SchemaOperation(
        operation_type=SchemaOperationType.ELEMENT_ADD,
        kind=CHANGED_KIND,
        section=SchemaOperationSection.ATTRIBUTES,
        element_name="color",
        value={"name": "color", "kind": "Text"},
    )
    migration = SchemaUpdateMigrationInfo(
        migration_name="node.attribute.add",
        path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind=CHANGED_KIND, field_name="color"),
    )
    diff = SchemaDiff(changed={CHANGED_KIND: HashableModelDiff(added={"color": None})})
    return RunInput(
        branch=Branch(name="runner-branch"),
        origin_schema=SchemaBranch(cache={}, name="runner-branch"),
        candidate=SchemaCandidate(
            operations=[operation],
            schema=SchemaBranch(cache={}, name="runner-branch"),
            validation=SchemaUpdateValidationResult(diff=diff, migrations=[migration]),
        ),
        at=Timestamp(),
        context=InfrahubContext(
            branch=BranchContext(name="runner-branch"),
            account=AccountSession(auth_type=AuthType.JWT, authenticated=True, account_id=USER_ID),
        ),
    )


async def _run(runner: SchemaChangeApplicationRunner, run_input: RunInput) -> str:
    return await runner.run(
        branch=run_input.branch,
        origin_schema=run_input.origin_schema,
        candidate=run_input.candidate,
        at=run_input.at,
        context=run_input.context,
        user_id=USER_ID,
    )


def _start_call(run_input: RunInput) -> SchemaApplicationCall:
    return SchemaApplicationCall(
        method=RECORDER_START,
        arguments={
            "branch": run_input.branch,
            "operations": run_input.candidate.operations,
            "at": run_input.at,
            "user_id": USER_ID,
        },
    )


def _execute_call(run_input: RunInput, application_id: str | None = RECORDED_APPLICATION_ID) -> SchemaApplicationCall:
    validation = run_input.candidate.validation
    return SchemaApplicationCall(
        method=EXECUTOR_EXECUTE,
        arguments={
            "branch": run_input.branch,
            "origin_schema": run_input.origin_schema,
            "rollback_schema": run_input.origin_schema,
            "candidate_schema": run_input.candidate.schema,
            "at": run_input.at,
            "context": run_input.context,
            "diff": validation.diff,
            "migrations": validation.migrations,
            "limit": [CHANGED_KIND],
            "user_id": USER_ID,
            "application_id": application_id,
        },
    )


def _recording(run_input: RunInput) -> SchemaChangeRecording:
    return SchemaChangeRecording(
        schema_change_id=RECORDED_SCHEMA_CHANGE_ID, application_id=RECORDED_APPLICATION_ID, at=run_input.at
    )


async def test_run_starts_then_executes_with_the_application_id_then_completes_and_returns_the_hash() -> None:
    calls: list[SchemaApplicationCall] = []
    runner = SchemaChangeApplicationRunner(
        recorder=RecordingApplicationRecorder(calls=calls),
        executor=RecordingSchemaUpdateExecutor(calls=calls, updated_hash=UPDATED_HASH),
    )
    run_input = _build_run_input()

    updated_hash = await _run(runner=runner, run_input=run_input)

    assert updated_hash == UPDATED_HASH
    assert calls == [
        _start_call(run_input),
        _execute_call(run_input),
        SchemaApplicationCall(
            method=RECORDER_COMPLETE,
            arguments={"recording": _recording(run_input), "branch": run_input.branch, "user_id": USER_ID},
        ),
    ]


@dataclass(frozen=True)
class ExecutorFailureCase:
    name: str
    error: Exception
    expected_text: str


EXECUTOR_FAILURE_CASES: list[ExecutorFailureCase] = [
    ExecutorFailureCase(
        name="infrahub_error_gives_its_message",
        error=MigrationError(message=MIGRATION_FAILURE),
        expected_text=MIGRATION_FAILURE,
    ),
    ExecutorFailureCase(
        name="other_error_gives_its_text",
        error=RuntimeError("Workflow is not available"),
        expected_text="Workflow is not available",
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in EXECUTOR_FAILURE_CASES])
async def test_run_records_the_failure_with_the_text_of_the_error_and_raises_the_same_exception(
    test_case: ExecutorFailureCase,
) -> None:
    calls: list[SchemaApplicationCall] = []
    runner = SchemaChangeApplicationRunner(
        recorder=RecordingApplicationRecorder(calls=calls),
        executor=FailingSchemaUpdateExecutor(calls=calls, error=test_case.error),
    )
    run_input = _build_run_input()

    with pytest.raises(type(test_case.error)) as exc_info:
        await _run(runner=runner, run_input=run_input)

    assert exc_info.value is test_case.error
    assert calls == [
        _start_call(run_input),
        _execute_call(run_input),
        SchemaApplicationCall(
            method=RECORDER_FAIL,
            arguments={"recording": _recording(run_input), "error": test_case.expected_text, "user_id": USER_ID},
        ),
    ]


async def test_run_raises_the_error_of_the_executor_and_logs_when_recording_the_failure_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls: list[SchemaApplicationCall] = []
    error = MigrationError(message=MIGRATION_FAILURE)
    runner = SchemaChangeApplicationRunner(
        recorder=FailingApplicationRecorder(calls=calls), executor=FailingSchemaUpdateExecutor(calls=calls, error=error)
    )
    run_input = _build_run_input()

    with caplog.at_level(logging.ERROR, logger="infrahub"), pytest.raises(MigrationError) as exc_info:
        await _run(runner=runner, run_input=run_input)

    assert exc_info.value is error
    assert [call.method for call in calls] == [RECORDER_START, EXECUTOR_EXECUTE, RECORDER_FAIL]
    failures = find_logged_events(
        caplog,
        event=RECORD_FAILURE_EVENT,
        schema_change_id=RECORDED_SCHEMA_CHANGE_ID,
        application_id=RECORDED_APPLICATION_ID,
    )
    assert len(failures) == 1
    assert failures[0]["exc_info"]


async def test_run_returns_the_hash_and_logs_when_recording_the_application_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls: list[SchemaApplicationCall] = []
    runner = SchemaChangeApplicationRunner(
        recorder=FailingCompleteApplicationRecorder(calls=calls),
        executor=RecordingSchemaUpdateExecutor(calls=calls, updated_hash=UPDATED_HASH),
    )
    run_input = _build_run_input()

    with caplog.at_level(logging.ERROR, logger="infrahub"):
        updated_hash = await _run(runner=runner, run_input=run_input)

    assert updated_hash == UPDATED_HASH
    assert [call.method for call in calls] == [RECORDER_START, EXECUTOR_EXECUTE, RECORDER_COMPLETE]
    failures = find_logged_events(
        caplog,
        event=RECORD_COMPLETION_EVENT,
        schema_change_id=RECORDED_SCHEMA_CHANGE_ID,
        application_id=RECORDED_APPLICATION_ID,
    )
    assert len(failures) == 1
    assert failures[0]["exc_info"]


async def test_run_applies_a_candidate_without_operations_without_recording_it_and_logs_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls: list[SchemaApplicationCall] = []
    runner = SchemaChangeApplicationRunner(
        recorder=RecordingApplicationRecorder(calls=calls),
        executor=RecordingSchemaUpdateExecutor(calls=calls, updated_hash=UPDATED_HASH),
    )
    run_input = _build_run_input()
    run_input = replace(run_input, candidate=replace(run_input.candidate, operations=[]))

    with caplog.at_level(logging.WARNING, logger="infrahub"):
        updated_hash = await _run(runner=runner, run_input=run_input)

    assert updated_hash == UPDATED_HASH
    assert calls == [_execute_call(run_input, application_id=None)]
    warnings = find_logged_events(caplog, event=NO_OPERATION_EVENT, branch=run_input.branch.name)
    assert len(warnings) == 1
