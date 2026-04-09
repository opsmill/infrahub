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
from infrahub.core.schema.definitions.core.template import core_object_template
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.db_snapshot import DbSnapshotter
from tests.helpers.db_validation import LATEST_ATTRIBUTE_PATH_STATUS_QUERY
from tests.helpers.edge_timestamps import assert_edge_timestamps


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


# ---------------------------------------------------------------------------
# Template fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def car_person_schema_with_template(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_unregistered: SchemaRoot
) -> SchemaBranch:
    """Schema where nbr_seats is NOT in a uniqueness constraint — templates include nbr_seats."""
    registry.schema.register_schema(schema=SchemaRoot(generics=[core_object_template]), branch=default_branch.name)
    for node in car_person_schema_unregistered.nodes:
        node.generate_template = True
    return registry.schema.register_schema(schema=car_person_schema_unregistered, branch=default_branch.name)


@pytest.fixture
async def car_person_schema_nbr_seats_in_constraint_with_template(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_unregistered: SchemaRoot
) -> SchemaBranch:
    """Schema where nbr_seats IS in a single-attr uniqueness constraint — templates exclude nbr_seats."""
    registry.schema.register_schema(schema=SchemaRoot(generics=[core_object_template]), branch=default_branch.name)
    car_node = next(n for n in car_person_schema_unregistered.nodes if n.name == "Car")
    car_node.uniqueness_constraints = [["name__value"], ["nbr_seats__value"]]
    for node in car_person_schema_unregistered.nodes:
        node.generate_template = True
    return registry.schema.register_schema(schema=car_person_schema_unregistered, branch=default_branch.name)


@pytest.fixture
async def car_template1_with_nbr_seats(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_with_template: SchemaBranch
) -> Node:
    """Template node created when nbr_seats is included in templates (not in a uniqueness constraint)."""
    template_person = await Node.init(db=db, schema="TemplateTestPerson", branch=default_branch)
    await template_person.new(db=db, template_name="template-person-1")
    await template_person.save(db=db)

    template = await Node.init(db=db, schema="TemplateTestCar", branch=default_branch)
    await template.new(db=db, template_name="template-car-1", nbr_seats=5, is_electric=False, owner=template_person)
    await template.save(db=db)
    return template


@pytest.fixture
async def car_template1_without_nbr_seats(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema_nbr_seats_in_constraint_with_template: SchemaBranch,
) -> Node:
    """Template node created when nbr_seats is excluded from templates (it's in a uniqueness constraint)."""
    template_person = await Node.init(db=db, schema="TemplateTestPerson", branch=default_branch)
    await template_person.new(db=db, template_name="template-person-1")
    await template_person.save(db=db)

    template = await Node.init(db=db, schema="TemplateTestCar", branch=default_branch)
    await template.new(db=db, template_name="template-car-1", is_electric=False, owner=template_person)
    await template.save(db=db)
    return template


# ---------------------------------------------------------------------------
# Template tests
# ---------------------------------------------------------------------------


async def test_migration_attribute_added_to_uniqueness_constraint_for_template(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema_with_template: SchemaBranch,
    car_template1_with_nbr_seats: Node,
) -> None:
    """Adding nbr_seats to a uniqueness constraint removes it from template nodes."""
    await assert_attribute_path_status(
        db=db,
        node_label="TemplateTestCar",
        attr_name="nbr_seats",
        branch_name=default_branch.name,
        expected_status="active",
    )

    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")

    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    new_car_schema.uniqueness_constraints = [["name__value"], ["nbr_seats__value"]]

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
        node_label="TemplateTestCar",
        attr_name="nbr_seats",
        branch_name=default_branch.name,
        expected_status="deleted",
    )


async def test_migration_attribute_removed_from_uniqueness_constraint_for_template(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema_nbr_seats_in_constraint_with_template: SchemaBranch,
    car_template1_without_nbr_seats: Node,
) -> None:
    """Removing nbr_seats from a uniqueness constraint adds it to template nodes."""
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")

    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    new_car_schema.uniqueness_constraints = [["name__value"]]
    new_car_schema.get_attribute("nbr_seats").unique = False

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
        node_label="TemplateTestCar",
        attr_name="nbr_seats",
        branch_name=default_branch.name,
        expected_status="active",
    )


async def test_migration_no_change_for_schema_without_template(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
    car_profile1_main: Node,
) -> None:
    """Migration does nothing for templates when generate_template=False."""
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")

    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    assert isinstance(new_car_schema, NodeSchema)
    new_car_schema.uniqueness_constraints = [["name__value", "nbr_seats__value"]]
    new_car_schema.generate_template = False

    migration = NodeUniquenessConstraintsUpdateMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=_make_schema_path("TestCar"),
    )

    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)

    # Profile migration still runs, but no template migration
    assert not execution_result.errors
