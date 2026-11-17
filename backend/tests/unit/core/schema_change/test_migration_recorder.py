from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from infrahub.core.constants import SchemaPathType
from infrahub.core.migrations.schema.models import SchemaMigrationPathResponseData
from infrahub.core.models import SchemaUpdateMigrationInfo
from infrahub.core.path import SchemaPath
from infrahub.core.schema_change.application_migration_recorder import ApplicationMigrationRecorder
from infrahub.core.schema_change.constants import SchemaChangeMigrationStatus
from tests.helpers.log import find_logged_events
from tests.unit.core.schema_change.helpers import (
    CREATE_MIGRATION_RECORDS,
    SET_MIGRATION_RECORDS_STATUS,
    FailingMigrationRecordStore,
    MigrationRecordStoreCall,
)

if TYPE_CHECKING:
    import pytest

APPLICATION_ID = "18a2cd5c-3f0b-4c41-9d3e-6a1d7c2b9e10"
MIGRATION_ERROR = "Unable to convert the value of 2 nodes"
REGISTER_FAILURE_EVENT = "Could not create the migration records of an application"
BATCH_FAILURE_EVENT = "Could not set the migration records of a batch to running"
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


async def test_register_logs_a_failure_to_create_the_records_and_does_not_raise(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = FailingMigrationRecordStore()
    recorder = ApplicationMigrationRecorder(store=store, application_id=APPLICATION_ID)

    with caplog.at_level(logging.WARNING, logger="infrahub"):
        await recorder.register(migrations=MIGRATIONS)

    assert store.calls == [CREATE_CALL]
    failures = find_logged_events(caplog, event=REGISTER_FAILURE_EVENT, application_id=APPLICATION_ID)
    assert len(failures) == 1
    assert failures[0]["exc_info"]


async def test_batch_started_logs_a_failure_to_update_the_records_and_does_not_raise(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = FailingMigrationRecordStore(failing_methods=frozenset({SET_MIGRATION_RECORDS_STATUS}))
    recorder = ApplicationMigrationRecorder(store=store, application_id=APPLICATION_ID)
    await recorder.register(migrations=MIGRATIONS)

    with caplog.at_level(logging.WARNING, logger="infrahub"):
        await recorder.batch_started(positions=[0, 1])

    assert store.calls == [
        CREATE_CALL,
        MigrationRecordStoreCall(
            method=SET_MIGRATION_RECORDS_STATUS,
            arguments={
                "record_ids": ["record-0", "record-1"],
                "status": SchemaChangeMigrationStatus.RUNNING,
                "nbr_migrations_executed": None,
                "errors": [],
            },
        ),
    ]
    failures = find_logged_events(caplog, event=BATCH_FAILURE_EVENT, application_id=APPLICATION_ID, positions=[0, 1])
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
                "record_ids": ["record-1"],
                "status": SchemaChangeMigrationStatus.FAILED,
                "nbr_migrations_executed": 2,
                "errors": [MIGRATION_ERROR],
            },
        ),
    ]
    failures = find_logged_events(caplog, event=MIGRATION_FAILURE_EVENT, application_id=APPLICATION_ID, position=1)
    assert len(failures) == 1
    assert failures[0]["exc_info"]
