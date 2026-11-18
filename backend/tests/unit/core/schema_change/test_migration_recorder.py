from __future__ import annotations

import logging
from dataclasses import dataclass

import pytest

from infrahub.core.constants import SchemaPathType
from infrahub.core.migrations.schema.models import SchemaMigrationPathResponseData
from infrahub.core.models import SchemaUpdateMigrationInfo
from infrahub.core.path import SchemaPath
from infrahub.core.schema_change.application_migration_recorder import ApplicationMigrationRecorder
from infrahub.core.schema_change.enums import SchemaChangeMigrationStatus
from infrahub.core.schema_change.factory import build_schema_change_repository
from infrahub.exceptions import DatabaseError, QueryError
from tests.helpers.log import find_logged_events
from tests.unit.core.schema_change.helpers import (
    CREATE_MIGRATION_RECORDS,
    FAILING_STORE_ERROR,
    SET_MIGRATION_RECORDS_STATUS,
    FailingMigrationRecordStore,
    MigrationRecordStoreCall,
    TransientFailingDatabase,
)

APPLICATION_ID = "18a2cd5c-3f0b-4c41-9d3e-6a1d7c2b9e10"
MIGRATION_ERROR = "Unable to convert the value of 2 nodes"
REGISTER_FAILURE_EVENT = "Could not create the migration records of an application"
STARTED_FAILURE_EVENT = "Could not set the migration record of a migration to running"
MIGRATION_FAILURE_EVENT = "Could not update the migration record of a migration"

MIGRATIONS = [
    SchemaUpdateMigrationInfo(
        migration_name="node.attribute.add",
        path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="color"),
    ),
    SchemaUpdateMigrationInfo(
        migration_name="attribute.kind.update",
        path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="name"),
    ),
]

CREATE_CALL = MigrationRecordStoreCall(
    method=CREATE_MIGRATION_RECORDS, arguments={"application_id": APPLICATION_ID, "migrations": MIGRATIONS}
)


@dataclass(frozen=True)
class StoreErrorCase:
    name: str
    error: Exception


STORE_ERROR_CASES = [
    StoreErrorCase(name="database_error", error=DatabaseError(message=FAILING_STORE_ERROR)),
    StoreErrorCase(
        name="query_error_when_the_application_is_missing",
        error=QueryError(query="MATCH (application) RETURN application", params={}),
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in STORE_ERROR_CASES])
async def test_register_logs_a_failure_to_create_the_records_and_does_not_raise(
    test_case: StoreErrorCase, caplog: pytest.LogCaptureFixture
) -> None:
    store = FailingMigrationRecordStore(error=test_case.error)
    recorder = ApplicationMigrationRecorder(store=store, application_id=APPLICATION_ID)

    with caplog.at_level(logging.WARNING, logger="infrahub"):
        await recorder.register(migrations=MIGRATIONS)

    assert store.calls == [CREATE_CALL]
    failures = find_logged_events(caplog, event=REGISTER_FAILURE_EVENT, application_id=APPLICATION_ID)
    assert len(failures) == 1
    assert failures[0]["exc_info"]


async def test_migration_started_logs_a_failure_to_update_the_record_and_does_not_raise(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = FailingMigrationRecordStore(failing_methods=frozenset({SET_MIGRATION_RECORDS_STATUS}))
    recorder = ApplicationMigrationRecorder(store=store, application_id=APPLICATION_ID)
    await recorder.register(migrations=MIGRATIONS)

    with caplog.at_level(logging.WARNING, logger="infrahub"):
        await recorder.migration_started(position=1)

    assert store.calls == [
        CREATE_CALL,
        MigrationRecordStoreCall(
            method=SET_MIGRATION_RECORDS_STATUS,
            arguments={
                "application_id": APPLICATION_ID,
                "positions": [1],
                "status": SchemaChangeMigrationStatus.RUNNING,
                "nbr_migrations_executed": None,
                "errors": [],
            },
        ),
    ]
    failures = find_logged_events(caplog, event=STARTED_FAILURE_EVENT, application_id=APPLICATION_ID, position=1)
    assert len(failures) == 1
    assert failures[0]["exc_info"]


async def test_migration_ended_logs_a_failure_to_update_the_record_and_does_not_raise(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = FailingMigrationRecordStore(failing_methods=frozenset({SET_MIGRATION_RECORDS_STATUS}))
    recorder = ApplicationMigrationRecorder(store=store, application_id=APPLICATION_ID)
    await recorder.register(migrations=MIGRATIONS)
    result = SchemaMigrationPathResponseData(
        migration_name=MIGRATIONS[1].migration_name,
        schema_path=MIGRATIONS[1].path,
        nbr_migrations_executed=2,
        errors=[MIGRATION_ERROR],
    )

    with caplog.at_level(logging.WARNING, logger="infrahub"):
        await recorder.migration_ended(position=1, result=result)

    assert store.calls == [
        CREATE_CALL,
        MigrationRecordStoreCall(
            method=SET_MIGRATION_RECORDS_STATUS,
            arguments={
                "application_id": APPLICATION_ID,
                "positions": [1],
                "status": SchemaChangeMigrationStatus.FAILED,
                "nbr_migrations_executed": 2,
                "errors": [MIGRATION_ERROR],
            },
        ),
    ]
    failures = find_logged_events(caplog, event=MIGRATION_FAILURE_EVENT, application_id=APPLICATION_ID, position=1)
    assert len(failures) == 1
    assert failures[0]["exc_info"]


CREATE_QUERY_NAME = "schema-change-migration-create"
STATUS_QUERY_NAME = "schema-change-migration-status-update"


@dataclass(frozen=True)
class TransientWriteCase:
    name: str
    nbr_failures: int
    """The number of status writes that fail with a transient error before the others succeed."""
    expected_nbr_status_writes: int
    expected_nbr_logged_failures: int


TRANSIENT_WRITE_CASES = [
    TransientWriteCase(
        name="one_transient_error_is_retried",
        nbr_failures=1,
        expected_nbr_status_writes=2,
        expected_nbr_logged_failures=0,
    ),
    TransientWriteCase(
        name="a_transient_error_on_every_attempt_is_logged",
        nbr_failures=100,
        expected_nbr_status_writes=3,
        expected_nbr_logged_failures=1,
    ),
]


@pytest.mark.usefixtures("fast_record_write_retries")
@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in TRANSIENT_WRITE_CASES])
async def test_migration_started_retries_a_transient_error_then_logs_the_failure(
    test_case: TransientWriteCase, caplog: pytest.LogCaptureFixture
) -> None:
    db = TransientFailingDatabase(failing_query_name=STATUS_QUERY_NAME, nbr_failures=test_case.nbr_failures)
    recorder = ApplicationMigrationRecorder(store=build_schema_change_repository(db=db), application_id=APPLICATION_ID)
    await recorder.register(migrations=MIGRATIONS)

    with caplog.at_level(logging.WARNING, logger="infrahub"):
        await recorder.migration_started(position=0)

    assert db.write_names == [CREATE_QUERY_NAME] + [STATUS_QUERY_NAME] * test_case.expected_nbr_status_writes
    failures = find_logged_events(caplog, event=STARTED_FAILURE_EVENT, application_id=APPLICATION_ID, position=0)
    assert len(failures) == test_case.expected_nbr_logged_failures
