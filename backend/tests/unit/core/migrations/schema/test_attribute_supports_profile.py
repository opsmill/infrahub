import uuid

from infrahub.core import registry
from infrahub.core.attribute import BaseAttribute
from infrahub.core.branch import Branch
from infrahub.core.constants import SchemaPathType
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.schema.attribute_supports_profile import (
    AttributeSupportsProfileUpdateMigration,
)
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.db_snapshot import DbSnapshotter
from tests.helpers.edge_timestamps import assert_edge_timestamps


async def test_migration_no_change_when_support_profiles_unchanged(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema, car_profile1_main: Node
) -> None:
    """Test that migration does nothing when support_profiles doesn't change."""
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")
    prev_attr = prev_car_schema.get_attribute(name="nbr_seats")
    prev_attr.id = str(uuid.uuid4())

    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    new_attr = new_car_schema.get_attribute(name="nbr_seats")
    new_attr.id = prev_attr.id
    # support_profiles is not changed

    migration = AttributeSupportsProfileUpdateMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="nbr_seats"),
    )

    execution_result = await migration.execute(db=db, branch=default_branch, at=Timestamp())
    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 0


async def test_migration_no_change_for_new_attribute(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema, car_profile1_main: Node
) -> None:
    """Test that migration does nothing for new attributes (no previous ID)."""
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")
    # Don't set an ID on previous attribute - indicates this is a new attribute

    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    new_attr = new_car_schema.get_attribute(name="nbr_seats")
    # support_profiles is computed from read_only and optional
    # To toggle it, we need to change those underlying properties
    new_attr.read_only = True  # This disables support_profiles

    migration = AttributeSupportsProfileUpdateMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="nbr_seats"),
    )

    execution_result = await migration.execute(db=db, branch=default_branch, at=Timestamp())
    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 0


async def test_migration_disable_support_profiles(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema, car_profile1_main: Node
) -> None:
    """Test disabling support_profiles removes attributes from profile nodes."""
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")
    prev_attr = prev_car_schema.get_attribute(name="nbr_seats")
    prev_attr.id = str(uuid.uuid4())

    nbr_seats_attr = car_profile1_main.get_attribute(name="nbr_seats")
    assert isinstance(nbr_seats_attr, BaseAttribute), "nbr_seats attribute should exist"
    nbr_seats_attr.value = 5
    await car_profile1_main.save(db=db)

    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    new_attr = new_car_schema.get_attribute(name="nbr_seats")
    new_attr.id = prev_attr.id
    # support_profiles is computed from read_only and optional
    # Setting read_only=True disables support_profiles
    new_attr.read_only = True

    migration = AttributeSupportsProfileUpdateMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="nbr_seats"),
    )

    execution_result = await migration.execute(db=db, branch=default_branch, at=Timestamp())
    assert not execution_result.errors

    fresh_car_profle = await NodeManager.get_one(db=db, id=car_profile1_main.id)
    nbr_seats_attr = fresh_car_profle.get_attribute(name="nbr_seats")
    assert nbr_seats_attr.value is None


async def test_migration_edge_timestamps(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema, car_profile1_main: Node
) -> None:
    """Verify edges created/modified during AttributeSupportsProfileUpdateMigration use the 'at' timestamp."""
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")
    prev_attr = prev_car_schema.get_attribute(name="nbr_seats")
    prev_attr.id = str(uuid.uuid4())

    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    new_attr = new_car_schema.get_attribute(name="nbr_seats")
    new_attr.id = prev_attr.id
    # support_profiles is computed from read_only and optional
    # Setting read_only=True disables support_profiles
    new_attr.read_only = True

    # 1. Snapshot before migration
    snapshotter = DbSnapshotter(db)
    before_snapshot = await snapshotter.snapshot()

    # 2. Create explicit timestamp
    at = Timestamp()
    at_str = at.to_string()

    # 3. Execute migration
    migration = AttributeSupportsProfileUpdateMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="nbr_seats"),
    )
    execution_result = await migration.execute(db=db, branch=default_branch, at=at)
    assert not execution_result.errors

    # 4. Validate edge timestamps
    after_snapshot = await snapshotter.snapshot()
    assert_edge_timestamps(before_snapshot, after_snapshot, at_str)
