from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from neo4j.exceptions import TransientError

from infrahub.core.constants import SYSTEM_USER_ID, SchemaPathType
from infrahub.core.models import SchemaUpdateMigrationInfo
from infrahub.core.path import SchemaPath
from infrahub.core.schema_change.enums import SchemaChangeMigrationStatus, SchemaOperationSection, SchemaOperationType
from infrahub.core.schema_change.factory import build_schema_change_repository
from infrahub.core.schema_change.operations import SchemaOperation
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabaseMode
from tests.unit.core.schema_change.helpers import TRANSIENT_ERROR, TransientFailingDatabase

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from infrahub.core.schema_change.repository import SchemaChangeRepository

SCHEMA_CHANGE_ID = "0c6f3e1a-9b2d-4e57-a8f4-3d1b7c9e2a60"
APPLICATION_ID = "6e2a8d41-1f7c-4b93-b5e0-8c4d2f9a1b37"
PARENT_ID = "a3d95b72-4c1e-4f80-9e26-7b1f0c8d5e49"


def _create_schema_change(repository: SchemaChangeRepository) -> Awaitable[object]:
    operation = SchemaOperation(
        operation_type=SchemaOperationType.ELEMENT_ADD,
        kind="TestCar",
        section=SchemaOperationSection.ATTRIBUTES,
        element_name="color",
        value={"name": "color", "kind": "Text"},
    )
    return repository.create_schema_change(
        branch="main", operations=[operation], at=Timestamp(), user_id=SYSTEM_USER_ID
    )


def _mark_applied(repository: SchemaChangeRepository) -> Awaitable[object]:
    return repository.mark_applied(
        schema_change_id=SCHEMA_CHANGE_ID,
        application_id=APPLICATION_ID,
        version=2,
        parent_id=PARENT_ID,
        applied_at=Timestamp(),
        user_id=SYSTEM_USER_ID,
    )


def _mark_failed(repository: SchemaChangeRepository) -> Awaitable[object]:
    return repository.mark_failed(
        schema_change_id=SCHEMA_CHANGE_ID, application_id=APPLICATION_ID, error="failed", user_id=SYSTEM_USER_ID
    )


def _create_migration_records(repository: SchemaChangeRepository) -> Awaitable[object]:
    migration = SchemaUpdateMigrationInfo(
        migration_name="node.attribute.add",
        path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="color"),
    )
    return repository.create_migration_records(application_id=APPLICATION_ID, migrations=[migration])


def _set_migration_records_status(repository: SchemaChangeRepository) -> Awaitable[object]:
    return repository.set_migration_records_status(
        application_id=APPLICATION_ID,
        positions=[0],
        status=SchemaChangeMigrationStatus.RUNNING,
        nbr_migrations_executed=None,
        errors=[],
    )


@dataclass(frozen=True)
class RecordWriteCase:
    name: str
    query_name: str
    write: Callable[[SchemaChangeRepository], Awaitable[object]]


RECORD_WRITE_CASES = [
    RecordWriteCase(name="create_schema_change", query_name="schema-change-create", write=_create_schema_change),
    RecordWriteCase(name="mark_applied", query_name="schema-change-mark-applied", write=_mark_applied),
    RecordWriteCase(name="mark_failed", query_name="schema-change-mark-failed", write=_mark_failed),
    RecordWriteCase(
        name="create_migration_records", query_name="schema-change-migration-create", write=_create_migration_records
    ),
    RecordWriteCase(
        name="set_migration_records_status",
        query_name="schema-change-migration-status-update",
        write=_set_migration_records_status,
    ),
]


@pytest.mark.usefixtures("fast_record_write_retries")
@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in RECORD_WRITE_CASES])
async def test_a_write_outside_a_transaction_runs_again_after_a_transient_error(test_case: RecordWriteCase) -> None:
    db = TransientFailingDatabase(failing_query_name=test_case.query_name, nbr_failures=1)

    await test_case.write(build_schema_change_repository(db=db))

    assert db.write_names == [test_case.query_name, test_case.query_name]


@pytest.mark.usefixtures("fast_record_write_retries")
@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in RECORD_WRITE_CASES])
async def test_a_write_in_a_transaction_raises_a_transient_error_without_running_again(
    test_case: RecordWriteCase,
) -> None:
    db = TransientFailingDatabase(
        failing_query_name=test_case.query_name, nbr_failures=1, mode=InfrahubDatabaseMode.TRANSACTION
    )

    with pytest.raises(TransientError, match=rf"^{TRANSIENT_ERROR}$"):
        await test_case.write(build_schema_change_repository(db=db))

    assert db.write_names == [test_case.query_name]
