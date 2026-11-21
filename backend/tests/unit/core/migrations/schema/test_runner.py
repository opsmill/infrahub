import logging
from uuid import uuid4

import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import SchemaPathType
from infrahub.core.migrations import MIGRATION_MAP
from infrahub.core.migrations.schema.models import SchemaApplyMigrationData, SchemaMigrationPathResponseData
from infrahub.core.migrations.schema.runner import SchemaMigrationRunner, SchemaPathMigrator
from infrahub.core.migrations.schema.scheduler import MigrationScheduler
from infrahub.core.models import SchemaUpdateMigrationInfo
from infrahub.core.timestamp import Timestamp
from tests.adapters.migration_recorder import (
    MIGRATION_ENDED,
    MIGRATION_STARTED,
    REGISTER,
    MigrationRecorderCall,
    RecordingMigrationRecorder,
)
from tests.unit.core.migrations.schema.helpers import (
    END,
    START,
    FailingMigrator,
    RecordingMigrator,
    full_schema_branch,
    path_migration,
)

LOG = logging.getLogger(__name__)
MAX_CONCURRENT_GROUPS = 5

INTERFACE_SERIAL_ADD = path_migration(
    migration_name="node.attribute.add", schema_kind="TestingInterface", field_name="serial"
)
PHYSICAL_SPEED_ADD = path_migration(
    migration_name="node.attribute.add", schema_kind="TestingPhysicalInterface", field_name="speed"
)
CAR_COLOR_ADD = path_migration(migration_name="node.attribute.add", schema_kind="TestingCar", field_name="color")
CAR_PAINT_RENAME = path_migration(
    migration_name="attribute.name.update", schema_kind="TestingCar", field_name="paint", property_name="name"
)
CAR_OWNER_REMOVE = path_migration(
    migration_name="node.relationship.remove",
    schema_kind="TestingCar",
    path_type=SchemaPathType.RELATIONSHIP,
    field_name="owner",
)
CAR_UNIQUE_UPDATE = path_migration(
    migration_name="attribute.unique.update", schema_kind="TestingCar", field_name="name", property_name="unique"
)
CAR_RENAME = path_migration(
    migration_name="node.name.update",
    schema_kind="TestingCar",
    path_type=SchemaPathType.NODE,
    field_name="name",
    property_name="name",
)
PHYSICAL_RENAME = path_migration(
    migration_name="node.name.update",
    schema_kind="TestingPhysicalInterface",
    path_type=SchemaPathType.NODE,
    field_name="name",
    property_name="name",
)


def _data(migrations: list[SchemaUpdateMigrationInfo]) -> SchemaApplyMigrationData:
    return SchemaApplyMigrationData(
        branch=Branch(name="main", uuid=uuid4()),
        previous_schema=full_schema_branch(),
        new_schema=full_schema_branch(),
        migrations=migrations,
        at=Timestamp(),
    )


def _runner(
    migrator: SchemaPathMigrator,
    recorder: RecordingMigrationRecorder | None = None,
    max_concurrent_groups: int = MAX_CONCURRENT_GROUPS,
) -> SchemaMigrationRunner:
    return SchemaMigrationRunner(
        scheduler=MigrationScheduler(migration_classes=MIGRATION_MAP),
        migrator=migrator,
        recorder=recorder or RecordingMigrationRecorder(),
        max_concurrent_groups=max_concurrent_groups,
        log=LOG,
    )


async def test_a_generic_and_an_inheriting_kind_do_not_run_at_the_same_time() -> None:
    migrator = RecordingMigrator(errors_by_field={})

    errors = await _runner(migrator=migrator).run(data=_data(migrations=[PHYSICAL_SPEED_ADD, INTERFACE_SERIAL_ADD]))

    assert errors == []
    assert migrator.events == [
        (START, "TestingInterface", "serial"),
        (END, "TestingInterface", "serial"),
        (START, "TestingPhysicalInterface", "speed"),
        (END, "TestingPhysicalInterface", "speed"),
    ]


async def test_unrelated_groups_run_at_the_same_time() -> None:
    migrator = RecordingMigrator(errors_by_field={})

    await _runner(migrator=migrator).run(data=_data(migrations=[PHYSICAL_SPEED_ADD, CAR_COLOR_ADD]))

    assert migrator.events == [
        (START, "TestingCar", "color"),
        (START, "TestingPhysicalInterface", "speed"),
        (END, "TestingCar", "color"),
        (END, "TestingPhysicalInterface", "speed"),
    ]


async def test_unrelated_groups_respect_the_concurrency_limit() -> None:
    migrator = RecordingMigrator(errors_by_field={})

    await _runner(migrator=migrator, max_concurrent_groups=1).run(
        data=_data(migrations=[PHYSICAL_SPEED_ADD, CAR_COLOR_ADD])
    )

    assert migrator.events == [
        (START, "TestingCar", "color"),
        (END, "TestingCar", "color"),
        (START, "TestingPhysicalInterface", "speed"),
        (END, "TestingPhysicalInterface", "speed"),
    ]


async def test_kind_updates_run_one_at_a_time() -> None:
    migrator = RecordingMigrator(errors_by_field={})

    await _runner(migrator=migrator).run(data=_data(migrations=[PHYSICAL_RENAME, CAR_RENAME]))

    assert migrator.events == [
        (START, "TestingCar", "name"),
        (END, "TestingCar", "name"),
        (START, "TestingPhysicalInterface", "name"),
        (END, "TestingPhysicalInterface", "name"),
    ]


async def test_phases_run_in_order() -> None:
    migrator = RecordingMigrator(errors_by_field={})

    await _runner(migrator=migrator).run(data=_data(migrations=[CAR_COLOR_ADD, CAR_PAINT_RENAME, CAR_OWNER_REMOVE]))

    assert migrator.events == [
        (START, "TestingCar", "owner"),
        (END, "TestingCar", "owner"),
        (START, "TestingCar", "paint"),
        (END, "TestingCar", "paint"),
        (START, "TestingCar", "color"),
        (END, "TestingCar", "color"),
    ]


async def test_each_record_starts_and_ends_around_its_migration() -> None:
    recorder = RecordingMigrationRecorder()

    await _runner(migrator=RecordingMigrator(errors_by_field={}), recorder=recorder).run(
        data=_data(migrations=[PHYSICAL_SPEED_ADD, INTERFACE_SERIAL_ADD])
    )

    assert recorder.calls == [
        MigrationRecorderCall(method=REGISTER, arguments={"migrations": [INTERFACE_SERIAL_ADD, PHYSICAL_SPEED_ADD]}),
        MigrationRecorderCall(method=MIGRATION_STARTED, arguments={"position": 0}),
        MigrationRecorderCall(
            method=MIGRATION_ENDED,
            arguments={
                "position": 0,
                "result": SchemaMigrationPathResponseData(
                    migration_name="node.attribute.add",
                    schema_path=INTERFACE_SERIAL_ADD.path,
                    errors=[],
                    nbr_migrations_executed=1,
                ),
            },
        ),
        MigrationRecorderCall(method=MIGRATION_STARTED, arguments={"position": 1}),
        MigrationRecorderCall(
            method=MIGRATION_ENDED,
            arguments={
                "position": 1,
                "result": SchemaMigrationPathResponseData(
                    migration_name="node.attribute.add",
                    schema_path=PHYSICAL_SPEED_ADD.path,
                    errors=[],
                    nbr_migrations_executed=1,
                ),
            },
        ),
    ]


async def test_an_error_stops_the_rest_of_its_group_and_later_phases() -> None:
    migrator = RecordingMigrator(errors_by_field={"serial": ["boom"]})

    errors = await _runner(migrator=migrator).run(
        data=_data(migrations=[INTERFACE_SERIAL_ADD, PHYSICAL_SPEED_ADD, CAR_UNIQUE_UPDATE])
    )

    assert errors == ["boom"]
    assert migrator.events == [(START, "TestingInterface", "serial"), (END, "TestingInterface", "serial")]


async def test_errors_from_every_group_of_a_phase_are_returned() -> None:
    recorder = RecordingMigrationRecorder()
    migrator = RecordingMigrator(errors_by_field={"color": ["car failed"], "speed": ["interface failed"]})

    errors = await _runner(migrator=migrator, recorder=recorder).run(
        data=_data(migrations=[CAR_COLOR_ADD, PHYSICAL_SPEED_ADD])
    )

    assert sorted(errors) == ["car failed", "interface failed"]
    assert [call.arguments["position"] for call in recorder.calls if call.method == MIGRATION_ENDED] == [0, 1]


async def test_an_exception_stops_the_run() -> None:
    recorder = RecordingMigrationRecorder()
    migrator = FailingMigrator(failing_fields={"owner"})

    with pytest.raises(RuntimeError, match=r"^migration failed: owner$"):
        await _runner(migrator=migrator, recorder=recorder).run(
            data=_data(migrations=[CAR_OWNER_REMOVE, CAR_COLOR_ADD])
        )

    assert migrator.events == [(START, "TestingCar", "owner")]
    assert [call.method for call in recorder.calls] == [REGISTER, MIGRATION_STARTED]


async def test_no_migrations_registers_nothing() -> None:
    recorder = RecordingMigrationRecorder()

    errors = await _runner(migrator=RecordingMigrator(errors_by_field={}), recorder=recorder).run(
        data=_data(migrations=[])
    )

    assert errors == []
    assert recorder.calls == []
