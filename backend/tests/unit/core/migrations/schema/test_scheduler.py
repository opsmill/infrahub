from dataclasses import dataclass

import pytest

from infrahub.core.constants import SchemaPathType
from infrahub.core.migrations import MIGRATION_MAP
from infrahub.core.migrations.schema.phases import MigrationPhase
from infrahub.core.migrations.schema.scheduler import MigrationSchedule, MigrationScheduler, PositionedMigration
from infrahub.core.models import SchemaUpdateMigrationInfo
from tests.unit.core.migrations.schema.helpers import full_schema_branch, path_migration, renamed_car_schema_branches

SCHEDULER = MigrationScheduler(migration_classes=MIGRATION_MAP)


def _schedule(migrations: list[SchemaUpdateMigrationInfo]) -> MigrationSchedule:
    return SCHEDULER.schedule(
        migrations=migrations, previous_schema=full_schema_branch(), new_schema=full_schema_branch()
    )


def test_positions_sort_by_phase_then_schema_path_then_migration_name() -> None:
    car_color_add = path_migration(migration_name="node.attribute.add", schema_kind="TestingCar", field_name="color")
    car_paint_rename = path_migration(
        migration_name="attribute.name.update", schema_kind="TestingCar", field_name="paint", property_name="name"
    )
    car_owner_remove = path_migration(
        migration_name="node.relationship.remove",
        schema_kind="TestingCar",
        path_type=SchemaPathType.RELATIONSHIP,
        field_name="owner",
    )
    person_rename = path_migration(
        migration_name="node.name.update",
        schema_kind="TestingPerson",
        path_type=SchemaPathType.NODE,
        property_name="name",
    )
    car_rename = path_migration(
        migration_name="node.name.update", schema_kind="TestingCar", path_type=SchemaPathType.NODE, property_name="name"
    )
    car_unique = path_migration(
        migration_name="attribute.unique.update", schema_kind="TestingCar", field_name="name", property_name="unique"
    )

    schedule = _schedule(
        migrations=[car_unique, car_color_add, person_rename, car_paint_rename, car_owner_remove, car_rename]
    )

    assert schedule.migrations == (
        PositionedMigration(position=0, migration=car_rename),
        PositionedMigration(position=1, migration=person_rename),
        PositionedMigration(position=2, migration=car_owner_remove),
        PositionedMigration(position=3, migration=car_paint_rename),
        PositionedMigration(position=4, migration=car_color_add),
        PositionedMigration(position=5, migration=car_unique),
    )
    assert [
        (scheduled.phase, [[member.position for member in group] for group in scheduled.groups])
        for scheduled in schedule.phases
    ] == [
        (MigrationPhase.KIND_UPDATE, [[0, 1]]),
        (MigrationPhase.FIELD_REMOVE, [[2]]),
        (MigrationPhase.ATTRIBUTE_RENAME, [[3]]),
        (MigrationPhase.ATTRIBUTE_ADD, [[4]]),
        (MigrationPhase.PROPERTY_UPDATE, [[5]]),
    ]


def test_positions_sort_by_schema_path_within_a_phase() -> None:
    car_color_kind = path_migration(migration_name="attribute.kind.update", schema_kind="TestCar", field_name="color")
    car_color_add = path_migration(migration_name="node.attribute.add", schema_kind="TestCar", field_name="color")
    car_name_kind = path_migration(
        migration_name="attribute.kind.update", schema_kind="TestCar", field_name="name", property_name="kind"
    )
    car_name = path_migration(migration_name="attribute.name.update", schema_kind="TestCar", field_name="name")
    car_rename = path_migration(
        migration_name="node.name.update", schema_kind="TestCar", path_type=SchemaPathType.NODE, property_name="name"
    )
    person_kind = path_migration(
        migration_name="node.inherit_from.update",
        schema_kind="TestPerson",
        path_type=SchemaPathType.NODE,
        property_name="inherit_from",
    )

    schedule = _schedule(migrations=[person_kind, car_name_kind, car_color_add, car_rename, car_name, car_color_kind])

    assert schedule.migrations == (
        PositionedMigration(position=0, migration=car_rename),
        PositionedMigration(position=1, migration=person_kind),
        PositionedMigration(position=2, migration=car_name),
        PositionedMigration(position=3, migration=car_color_kind),
        PositionedMigration(position=4, migration=car_name_kind),
        PositionedMigration(position=5, migration=car_color_add),
    )


def test_a_migration_without_a_class_is_refused() -> None:
    migration = path_migration(
        migration_name="relationship.direction.update",
        schema_kind="TestingCar",
        path_type=SchemaPathType.RELATIONSHIP,
        field_name="owner",
        property_name="direction",
    )

    with pytest.raises(
        ValueError,
        match=r"^No migration class for 'relationship\.direction\.update' on 'schema/TestingCar/owner/direction'$",
    ):
        _schedule(migrations=[migration])


def test_no_migrations_give_an_empty_schedule() -> None:
    assert _schedule(migrations=[]) == MigrationSchedule(migrations=(), phases=())


@dataclass(frozen=True, kw_only=True)
class GroupingCase:
    name: str
    migrations: list[SchemaUpdateMigrationInfo]
    expected_phase: MigrationPhase
    expected_groups: list[list[str | None]]


GROUPING_CASES: list[GroupingCase] = [
    GroupingCase(
        name="kind_updates_form_one_group",
        migrations=[
            path_migration(
                migration_name="node.name.update",
                schema_kind="TestingCar",
                path_type=SchemaPathType.NODE,
                field_name="name",
                property_name="name",
            ),
            path_migration(
                migration_name="node.name.update",
                schema_kind="TestingPhysicalInterface",
                path_type=SchemaPathType.NODE,
                field_name="name",
                property_name="name",
            ),
        ],
        expected_phase=MigrationPhase.KIND_UPDATE,
        expected_groups=[["name", "name"]],
    ),
    GroupingCase(
        name="generic_and_inheriting_kind_together",
        migrations=[
            path_migration(migration_name="node.attribute.add", schema_kind="TestingInterface", field_name="serial"),
            path_migration(migration_name="node.attribute.add", schema_kind="TestingCar", field_name="color"),
            path_migration(
                migration_name="node.attribute.add", schema_kind="TestingPhysicalInterface", field_name="speed"
            ),
        ],
        expected_phase=MigrationPhase.ATTRIBUTE_ADD,
        expected_groups=[["color"], ["serial", "speed"]],
    ),
    GroupingCase(
        name="both_sides_of_a_removed_relationship_together",
        migrations=[
            path_migration(
                migration_name="node.relationship.remove",
                schema_kind="TestingPerson",
                path_type=SchemaPathType.RELATIONSHIP,
                field_name="cars",
            ),
            path_migration(
                migration_name="node.relationship.remove",
                schema_kind="TestingCar",
                path_type=SchemaPathType.RELATIONSHIP,
                field_name="owner",
            ),
        ],
        expected_phase=MigrationPhase.FIELD_REMOVE,
        expected_groups=[["owner", "cars"]],
    ),
    GroupingCase(
        name="a_later_migration_joins_two_groups",
        migrations=[
            path_migration(
                migration_name="node.relationship.remove",
                schema_kind="TestingPerson",
                path_type=SchemaPathType.RELATIONSHIP,
                field_name="cars",
            ),
            path_migration(migration_name="node.attribute.remove", schema_kind="TestingPerson", field_name="age"),
            path_migration(migration_name="node.attribute.remove", schema_kind="TestingCar", field_name="color"),
        ],
        expected_phase=MigrationPhase.FIELD_REMOVE,
        expected_groups=[["color", "age", "cars"]],
    ),
    GroupingCase(
        name="unrelated_kinds_apart",
        migrations=[
            path_migration(
                migration_name="node.attribute.add", schema_kind="TestingPhysicalInterface", field_name="speed"
            ),
            path_migration(migration_name="node.attribute.add", schema_kind="TestingCar", field_name="color"),
        ],
        expected_phase=MigrationPhase.ATTRIBUTE_ADD,
        expected_groups=[["color"], ["speed"]],
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in GROUPING_CASES])
def test_groups_of_a_phase(case: GroupingCase) -> None:
    schedule = _schedule(migrations=case.migrations)

    assert [
        (scheduled.phase, [[member.migration.path.field_name for member in group] for group in scheduled.groups])
        for scheduled in schedule.phases
    ] == [(case.expected_phase, case.expected_groups)]


def test_both_sides_of_a_removed_relationship_stay_together_when_the_kind_is_renamed() -> None:
    previous_schema, new_schema = renamed_car_schema_branches()
    migrations = [
        path_migration(
            migration_name="node.name.update",
            schema_kind="TestingAuto",
            path_type=SchemaPathType.NODE,
            field_name="name",
            property_name="name",
        ),
        path_migration(
            migration_name="node.relationship.remove",
            schema_kind="TestingAuto",
            path_type=SchemaPathType.RELATIONSHIP,
            field_name="owner",
        ),
        path_migration(
            migration_name="node.relationship.remove",
            schema_kind="TestingPerson",
            path_type=SchemaPathType.RELATIONSHIP,
            field_name="cars",
        ),
    ]

    schedule = SCHEDULER.schedule(migrations=migrations, previous_schema=previous_schema, new_schema=new_schema)

    assert [
        (scheduled.phase, [[member.migration.path.field_name for member in group] for group in scheduled.groups])
        for scheduled in schedule.phases
    ] == [
        (MigrationPhase.KIND_UPDATE, [["name"]]),
        (MigrationPhase.FIELD_REMOVE, [["owner", "cars"]]),
    ]
