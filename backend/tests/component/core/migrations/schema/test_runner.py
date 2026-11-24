from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import BranchSupportType, RelationshipStatus, SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations import MIGRATION_MAP
from infrahub.core.migrations.schema.models import SchemaApplyMigrationData, SchemaMigrationPathResponseData
from infrahub.core.migrations.schema.runner import SchemaMigrationRunner
from infrahub.core.migrations.schema.scheduler import MigrationScheduler
from infrahub.core.migrations.schema.tasks import MAX_CONCURRENT_MIGRATION_GROUPS, TaskSchemaPathMigrator
from infrahub.core.models import SchemaUpdateMigrationInfo
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema_change.migration_recorder import NoRecordMigrationRecorder
from infrahub.core.timestamp import Timestamp
from infrahub.database.validation import verify_graph
from tests.adapters.migration_recorder import (
    MIGRATION_ENDED,
    MIGRATION_STARTED,
    REGISTER,
    MigrationRecorderCall,
    RecordingMigrationRecorder,
)
from tests.component.core.migrations.schema.second_run_helpers import register_candidate
from tests.helpers.db_validation import assert_attribute_path_status

if TYPE_CHECKING:
    from collections.abc import Callable

    from infrahub.core.branch import Branch
    from infrahub.core.schema.node_schema import NodeSchema
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.schema_change.migration_recorder import MigrationRecorder
    from infrahub.database import InfrahubDatabase


def _runner(db: InfrahubDatabase, recorder: MigrationRecorder) -> SchemaMigrationRunner:
    return SchemaMigrationRunner(
        scheduler=MigrationScheduler(migration_classes=MIGRATION_MAP),
        migrator=TaskSchemaPathMigrator(database=db),
        recorder=recorder,
        max_concurrent_groups=MAX_CONCURRENT_MIGRATION_GROUPS,
        log=logging.getLogger(__name__),
    )


async def _store_schema_ids(db: InfrahubDatabase, default_branch: Branch) -> None:
    """Store the registered schema, so that its elements get the IDs that let the diff see a rename."""
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    await registry.schema.load_schema_to_db(schema=schema, branch=default_branch, db=db, at=Timestamp())


async def _load_car_change(
    db: InfrahubDatabase, branch: Branch, change_car: Callable[[NodeSchema], None], expected_migration_names: list[str]
) -> None:
    """Change the `TestCar` schema of the branch as a schema load does, and run the migrations the change gives."""
    previous_schema = registry.schema.get_schema_branch(name=branch.name).duplicate()
    candidate = previous_schema.duplicate()
    car_schema = candidate.get_node(name="TestCar")
    change_car(car_schema)
    candidate.set(name="TestCar", schema=car_schema)
    await register_candidate(db=db, branch=branch, candidate=candidate)
    validation = previous_schema.validate_update(other=candidate, diff=previous_schema.diff(other=candidate))
    assert sorted(migration.migration_name for migration in validation.migrations) == expected_migration_names

    errors = await _runner(db=db, recorder=NoRecordMigrationRecorder()).run(
        data=SchemaApplyMigrationData(
            branch=branch,
            previous_schema=previous_schema,
            new_schema=candidate,
            migrations=validation.migrations,
            at=Timestamp(),
        )
    )

    assert errors == []


def _rename_color_and_add_a_new_color(car_schema: NodeSchema) -> None:
    car_schema.get_attribute(name="color").name = "paint"
    car_schema.attributes.append(AttributeSchema(name="color", kind="Text", optional=True, default_value="red"))


async def _car_ids(db: InfrahubDatabase, branch: Branch, filters: dict[str, object]) -> list[str]:
    """Return the cars whose stored attributes match; a loaded node would show the default of a missing attribute."""
    cars = await NodeManager.query(db=db, branch=branch, schema="TestCar", filters=filters)
    return [car.id for car in cars]


async def test_a_migration_reports_that_it_started_before_it_reports_its_result(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch, car_accord_main: Node
) -> None:
    previous_schema = registry.schema.get_schema_branch(name=default_branch.name)
    new_car_schema = previous_schema.get_node(name="TestCar", duplicate=False).duplicate()
    new_car_schema.attributes.append(AttributeSchema(name="smell", kind="Text", branch=BranchSupportType.AWARE))
    new_schema = previous_schema.duplicate()
    new_schema.set(name="TestCar", schema=new_car_schema)
    migration = SchemaUpdateMigrationInfo(
        path=SchemaPath(schema_kind="TestCar", path_type=SchemaPathType.ATTRIBUTE, field_name="smell"),
        migration_name="node.attribute.add",
    )
    recorder = RecordingMigrationRecorder()

    errors = await _runner(db=db, recorder=recorder).run(
        data=SchemaApplyMigrationData(
            branch=default_branch,
            previous_schema=previous_schema,
            new_schema=new_schema,
            migrations=[migration],
            at=Timestamp(),
        )
    )

    assert errors == []
    assert recorder.calls == [
        MigrationRecorderCall(method=REGISTER, arguments={"migrations": [migration]}),
        MigrationRecorderCall(method=MIGRATION_STARTED, arguments={"position": 0}),
        MigrationRecorderCall(
            method=MIGRATION_ENDED,
            arguments={
                "position": 0,
                "result": SchemaMigrationPathResponseData(
                    migration_name="node.attribute.add",
                    schema_path=migration.path,
                    errors=[],
                    nbr_migrations_executed=1,
                ),
            },
        ),
    ]


async def test_an_attribute_renamed_while_a_new_attribute_takes_its_name(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_schema_db: None,
    car_person_schema: SchemaBranch,
    car_accord_main: Node,
) -> None:
    assert await _car_ids(db=db, branch=default_branch, filters={"color__value": "#444444"}) == [car_accord_main.id]
    await _store_schema_ids(db=db, default_branch=default_branch)

    await _load_car_change(
        db=db,
        branch=default_branch,
        change_car=_rename_color_and_add_a_new_color,
        expected_migration_names=["attribute.name.update", "node.attribute.add"],
    )

    assert await _car_ids(db=db, branch=default_branch, filters={"paint__value": "#444444"}) == [car_accord_main.id]
    assert await _car_ids(db=db, branch=default_branch, filters={"color__value": "red"}) == [car_accord_main.id]
    await verify_graph(db=db, kinds=["TestCar"])


async def test_an_attribute_renamed_while_a_new_attribute_takes_its_name_on_a_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_schema_db: None,
    car_person_schema: SchemaBranch,
    car_accord_main: Node,
) -> None:
    await _store_schema_ids(db=db, default_branch=default_branch)
    branch = await create_branch(db=db, branch_name="rename-and-reuse")

    await _load_car_change(
        db=db,
        branch=branch,
        change_car=_rename_color_and_add_a_new_color,
        expected_migration_names=["attribute.name.update", "node.attribute.add"],
    )

    assert await _car_ids(db=db, branch=branch, filters={"paint__value": "#444444"}) == [car_accord_main.id]
    assert await _car_ids(db=db, branch=branch, filters={"color__value": "red"}) == [car_accord_main.id]
    assert await _car_ids(db=db, branch=default_branch, filters={"color__value": "#444444"}) == [car_accord_main.id]
    await verify_graph(db=db, kinds=["TestCar"])


async def test_an_attribute_removed_while_another_attribute_is_renamed_onto_its_name(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_schema_db: None,
    car_person_schema: SchemaBranch,
    person_john_main: Node,
) -> None:
    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(db=db, name="civic", nbr_seats=4, is_electric=False, transmission="manual", owner=person_john_main.id)
    await car.save(db=db)
    await _store_schema_ids(db=db, default_branch=default_branch)

    def remove_color_and_rename_transmission(car_schema: NodeSchema) -> None:
        car_schema.attributes = [attribute for attribute in car_schema.attributes if attribute.name != "color"]
        car_schema.get_attribute(name="transmission").name = "color"

    await _load_car_change(
        db=db,
        branch=default_branch,
        change_car=remove_color_and_rename_transmission,
        expected_migration_names=["attribute.name.update", "node.attribute.remove"],
    )

    assert await _car_ids(db=db, branch=default_branch, filters={"color__value": "manual"}) == [car.id]
    await verify_graph(db=db, kinds=["TestCar"])


@pytest.mark.xfail(
    strict=True,
    raises=ValueError,
    reason="the profile and template attribute migration finds the previous attribute by its new name, so a rename in the same load raises",
)
async def test_an_attribute_renamed_and_made_unique_leaves_the_profiles(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_schema_db: None,
    car_person_schema: SchemaBranch,
    car_accord_main: Node,
    car_profile1_main: Node,
) -> None:
    await assert_attribute_path_status(
        db=db,
        node_label="ProfileTestCar",
        attr_name="transmission",
        branch_name=default_branch.name,
        expected_status=RelationshipStatus.ACTIVE.value,
    )
    await _store_schema_ids(db=db, default_branch=default_branch)

    def rename_transmission_and_make_it_unique(car_schema: NodeSchema) -> None:
        transmission = car_schema.get_attribute(name="transmission")
        transmission.name = "gearbox"
        transmission.unique = True

    await _load_car_change(
        db=db,
        branch=default_branch,
        change_car=rename_transmission_and_make_it_unique,
        expected_migration_names=[
            "attribute.name.update",
            "attribute.unique.update",
            "node.uniqueness_constraints.update",
        ],
    )

    await assert_attribute_path_status(
        db=db,
        node_label="ProfileTestCar",
        attr_name="gearbox",
        branch_name=default_branch.name,
        expected_status=RelationshipStatus.DELETED.value,
    )
    await assert_attribute_path_status(
        db=db,
        node_label="TestCar",
        attr_name="gearbox",
        branch_name=default_branch.name,
        expected_status=RelationshipStatus.ACTIVE.value,
    )
    await verify_graph(db=db, kinds=["TestCar", "ProfileTestCar"])
