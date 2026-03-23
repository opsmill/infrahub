import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SchemaPathType
from infrahub.core.migrations.schema.node_uniqueness_constraints_update import (
    NodeUniquenessConstraintsUpdateMigration,
)
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.db_snapshot import DbSnapshotter
from tests.helpers.edge_timestamps import assert_edge_timestamps

LATEST_ATTRIBUTE_PATH_STATUS_QUERY = """
MATCH (node:%(label)s)
CALL (node) {
    MATCH (node)-[r1:HAS_ATTRIBUTE]->(attr:Attribute {name: $attr_name})
    WHERE r1.branch = $branch_name
    RETURN r1, attr
    ORDER BY r1.branch_level DESC, r1.from DESC
    LIMIT 1
}
CALL (attr) {
    MATCH (attr)-[r2:HAS_VALUE]->(av)
    WHERE r2.branch = $branch_name
    RETURN r2
    ORDER BY r2.branch_level DESC, r2.from DESC
    LIMIT 1
}
RETURN node.uuid AS node_id, r1.status AS has_attr_status, r2.status AS has_val_status
"""


async def assert_attribute_path_status(
    db: InfrahubDatabase,
    node_label: str,
    attr_name: str,
    branch_name: str,
    expected_status: str,
) -> None:
    query = LATEST_ATTRIBUTE_PATH_STATUS_QUERY % {"label": node_label}
    results = await db.execute_query(query=query, params={"attr_name": attr_name, "branch_name": branch_name})
    assert len(results) > 0, f"No {node_label} nodes found with attribute {attr_name!r}"
    for record in results:
        assert record["has_attr_status"] == expected_status, (
            f"Node {record['node_id']}: HAS_ATTRIBUTE status is {record['has_attr_status']!r}, expected {expected_status!r}"
        )
        assert record["has_val_status"] == expected_status, (
            f"Node {record['node_id']}: HAS_VALUE status is {record['has_val_status']!r}, expected {expected_status!r}"
        )


def _make_schema_path(schema_kind: str) -> SchemaPath:
    return SchemaPath(
        path_type=SchemaPathType.NODE,
        schema_kind=schema_kind,
        field_name="uniqueness_constraints",
        property_name="uniqueness_constraints",
    )


@pytest.fixture
async def car_person_schema(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_unregistered: SchemaRoot
) -> SchemaBranch:
    """Schema where nbr_seats is NOT in a uniqueness constraint — profiles include nbr_seats."""
    return registry.schema.register_schema(schema=car_person_schema_unregistered, branch=default_branch.name)


@pytest.fixture
async def car_person_schema_nbr_seats_in_constraint(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_unregistered: SchemaRoot
) -> SchemaBranch:
    """Schema where nbr_seats IS in a uniqueness constraint — profiles exclude nbr_seats."""
    car_node = next(n for n in car_person_schema_unregistered.nodes if n.name == "Car")
    car_node.uniqueness_constraints = [["name__value", "nbr_seats__value"]]
    return registry.schema.register_schema(schema=car_person_schema_unregistered, branch=default_branch.name)


@pytest.fixture
async def car_profile1_main(db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch) -> Node:
    profile = await Node.init(db=db, schema="ProfileTestCar", branch=default_branch)
    await profile.new(db=db, profile_name="car-profile1", nbr_seats=5, is_electric=False)
    await profile.save(db=db)
    return profile


@pytest.fixture
async def car_profile1_no_nbr_seats(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_nbr_seats_in_constraint: SchemaBranch
) -> Node:
    """Profile node created when nbr_seats is excluded from profiles (it's in a uniqueness constraint)."""
    profile = await Node.init(db=db, schema="ProfileTestCar", branch=default_branch)
    await profile.new(db=db, profile_name="car-profile1", is_electric=False)
    await profile.save(db=db)
    return profile


async def test_migration_attribute_added_to_uniqueness_constraint(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
    car_profile1_main: Node,
) -> None:
    """Adding nbr_seats to a uniqueness constraint removes it from profile nodes."""
    await assert_attribute_path_status(
        db=db,
        node_label="ProfileTestCar",
        attr_name="nbr_seats",
        branch_name=default_branch.name,
        expected_status="active",
    )

    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")

    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    new_car_schema.uniqueness_constraints = [["name__value", "nbr_seats__value"]]

    migration = NodeUniquenessConstraintsUpdateMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=_make_schema_path("TestCar"),
    )

    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)

    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed > 0
    await assert_attribute_path_status(
        db=db,
        node_label="ProfileTestCar",
        attr_name="nbr_seats",
        branch_name=default_branch.name,
        expected_status="deleted",
    )


async def test_migration_attribute_removed_from_uniqueness_constraint(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema_nbr_seats_in_constraint: SchemaBranch,
    car_profile1_no_nbr_seats: Node,
) -> None:
    """Removing nbr_seats from a uniqueness constraint adds it to profile nodes."""
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")

    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    new_car_schema.uniqueness_constraints = [["name__value"]]

    migration = NodeUniquenessConstraintsUpdateMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=_make_schema_path("TestCar"),
    )

    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)

    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed > 0
    await assert_attribute_path_status(
        db=db,
        node_label="ProfileTestCar",
        attr_name="nbr_seats",
        branch_name=default_branch.name,
        expected_status="active",
    )


async def test_migration_no_change_when_optional_attr_not_affected(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
    car_profile1_main: Node,
) -> None:
    """Uniqueness constraint changes that don't involve optional+support_profiles attrs produce no migrations."""
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")

    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    new_car_schema.uniqueness_constraints = [["name__value"]]

    migration = NodeUniquenessConstraintsUpdateMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=_make_schema_path("TestCar"),
    )

    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)

    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 0


async def test_migration_no_change_for_schema_without_profile(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
    car_profile1_main: Node,
) -> None:
    """Migration does nothing when the schema has generate_profile=False."""
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")

    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    new_car_schema.uniqueness_constraints = [["name__value", "nbr_seats__value"]]
    new_car_schema.generate_profile = False

    migration = NodeUniquenessConstraintsUpdateMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=_make_schema_path("TestCar"),
    )

    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)

    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 0
    # Profile attribute should be untouched
    await assert_attribute_path_status(
        db=db,
        node_label="ProfileTestCar",
        attr_name="nbr_seats",
        branch_name=default_branch.name,
        expected_status="active",
    )


async def test_migration_edge_timestamps(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
    car_profile1_main: Node,
) -> None:
    """Edges created/modified during migration use the 'at' timestamp."""
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")

    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    new_car_schema.uniqueness_constraints = [["name__value", "nbr_seats__value"]]

    snapshotter = DbSnapshotter(db)
    before_snapshot = await snapshotter.snapshot()

    at = Timestamp()

    migration = NodeUniquenessConstraintsUpdateMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=_make_schema_path("TestCar"),
    )
    execution_result = await migration.execute(migration_input=MigrationInput(db=db, at=at), branch=default_branch)

    assert not execution_result.errors
    after_snapshot = await snapshotter.snapshot()
    assert_edge_timestamps(before_snapshot, after_snapshot, at.to_string())
