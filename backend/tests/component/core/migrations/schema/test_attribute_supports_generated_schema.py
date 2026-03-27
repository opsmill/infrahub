import uuid

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType, RelationshipCardinality, RelationshipKind, SchemaPathType
from infrahub.core.migrations.schema.attribute_supports_generated_schema import (
    AttributeSupportsGeneratedSchemaMigration,
)
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.definitions.core.template import core_object_component_template, core_object_template
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.schema.relationship_schema import RelationshipSchema
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
    """Assert that the latest HAS_ATTRIBUTE->HAS_VALUE path has the expected status for all instances."""
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


@pytest.fixture
async def car_person_schema(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_unregistered: SchemaRoot
) -> SchemaBranch:
    registry.schema.register_schema(schema=SchemaRoot(generics=[core_object_template]), branch=default_branch.name)
    for node in car_person_schema_unregistered.nodes:
        node.generate_template = True
    return registry.schema.register_schema(schema=car_person_schema_unregistered, branch=default_branch.name)


@pytest.fixture
async def car_profile1_main(db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch) -> Node:
    profile = await Node.init(db=db, schema="ProfileTestCar", branch=default_branch)
    await profile.new(db=db, profile_name="car-profile1", nbr_seats=5, is_electric=False)
    await profile.save(db=db)
    return profile


@pytest.fixture
async def car_template1_main(db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch) -> Node:
    template_person = await Node.init(db=db, schema="TemplateTestPerson", branch=default_branch)
    await template_person.new(db=db, template_name="Template Person 1")
    await template_person.save(db=db)

    template = await Node.init(db=db, schema="TemplateTestCar", branch=default_branch)
    await template.new(db=db, template_name="Template Car 1", nbr_seats=5, is_electric=False, owner=template_person)
    await template.save(db=db)
    return template


@pytest.fixture
async def car_person_schema_read_only_seats(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_unregistered: SchemaRoot
) -> SchemaBranch:
    registry.schema.register_schema(schema=SchemaRoot(generics=[core_object_template]), branch=default_branch.name)
    for node in car_person_schema_unregistered.nodes:
        node.generate_template = True
    car_node = next(n for n in car_person_schema_unregistered.nodes if n.name == "Car")
    nbr_seats_attr = next(a for a in car_node.attributes if a.name == "nbr_seats")
    nbr_seats_attr.read_only = True
    return registry.schema.register_schema(schema=car_person_schema_unregistered, branch=default_branch.name)


async def test_migration_enable_support(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema_read_only_seats: SchemaBranch,
) -> None:
    """Test enabling support adds attributes to both profile and template nodes."""
    # Create profile and template nodes — they won't have nbr_seats (it's read_only)
    profile = await Node.init(db=db, schema="ProfileTestCar", branch=default_branch)
    await profile.new(db=db, profile_name="car-profile1", is_electric=False)
    await profile.save(db=db)

    template_person = await Node.init(db=db, schema="TemplateTestPerson", branch=default_branch)
    await template_person.new(db=db, template_name="Template Person 1")
    await template_person.save(db=db)

    template = await Node.init(db=db, schema="TemplateTestCar", branch=default_branch)
    await template.new(db=db, template_name="Template Car 1", is_electric=False, owner=template_person)
    await template.save(db=db)

    # Verify nbr_seats is not accessible on profile or template
    with pytest.raises(ValueError):
        profile.get_attribute(name="nbr_seats")
    with pytest.raises(ValueError):
        template.get_attribute(name="nbr_seats")

    # Set up migration: read_only=True -> read_only=False (enables support)
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")
    prev_attr = prev_car_schema.get_attribute(name="nbr_seats")
    prev_attr.id = str(uuid.uuid4())

    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    new_attr = new_car_schema.get_attribute(name="nbr_seats")
    new_attr.id = prev_attr.id
    new_attr.read_only = False
    candidate_schema.set(name="TestCar", schema=new_car_schema)

    migration = AttributeSupportsGeneratedSchemaMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="nbr_seats"),
    )

    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not execution_result.errors

    # Verify attribute path is active on profile and template nodes
    await assert_attribute_path_status(
        db=db,
        node_label="ProfileTestCar",
        attr_name="nbr_seats",
        branch_name=default_branch.name,
        expected_status="active",
    )
    await assert_attribute_path_status(
        db=db,
        node_label="TemplateTestCar",
        attr_name="nbr_seats",
        branch_name=default_branch.name,
        expected_status="active",
    )


async def test_migration_no_change_when_support_unchanged(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
    car_profile1_main: Node,
    car_template1_main: Node,
) -> None:
    """Test that migration does nothing when support_profiles and support_templates don't change."""
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")
    prev_attr = prev_car_schema.get_attribute(name="nbr_seats")
    prev_attr.id = str(uuid.uuid4())

    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    new_attr = new_car_schema.get_attribute(name="nbr_seats")
    new_attr.id = prev_attr.id

    migration = AttributeSupportsGeneratedSchemaMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="nbr_seats"),
    )

    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 0


async def test_migration_no_change_for_new_attribute(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
    car_profile1_main: Node,
    car_template1_main: Node,
) -> None:
    """Test that migration does nothing for new attributes (no previous ID)."""
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")

    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    new_attr = new_car_schema.get_attribute(name="nbr_seats")
    new_attr.read_only = True

    migration = AttributeSupportsGeneratedSchemaMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="nbr_seats"),
    )

    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 0


async def test_migration_disable_support(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
    car_profile1_main: Node,
    car_template1_main: Node,
) -> None:
    """Test disabling support removes attributes from both profile and template nodes."""
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")
    prev_attr = prev_car_schema.get_attribute(name="nbr_seats")
    prev_attr.id = str(uuid.uuid4())

    # Verify attribute path is active on profile and template before migration
    await assert_attribute_path_status(
        db=db,
        node_label="ProfileTestCar",
        attr_name="nbr_seats",
        branch_name=default_branch.name,
        expected_status="active",
    )
    await assert_attribute_path_status(
        db=db,
        node_label="TemplateTestCar",
        attr_name="nbr_seats",
        branch_name=default_branch.name,
        expected_status="active",
    )

    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    new_attr = new_car_schema.get_attribute(name="nbr_seats")
    new_attr.id = prev_attr.id
    new_attr.read_only = True

    migration = AttributeSupportsGeneratedSchemaMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="nbr_seats"),
    )

    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not execution_result.errors

    # Verify attribute path is deleted on profile and template nodes
    await assert_attribute_path_status(
        db=db,
        node_label="ProfileTestCar",
        attr_name="nbr_seats",
        branch_name=default_branch.name,
        expected_status="deleted",
    )
    await assert_attribute_path_status(
        db=db,
        node_label="TemplateTestCar",
        attr_name="nbr_seats",
        branch_name=default_branch.name,
        expected_status="deleted",
    )


def _device_part_schema_root(part_serial_read_only: bool = False) -> SchemaRoot:
    """Schema with Device (generate_template=True) having a Component relationship to Part.

    Part has generate_template=False but gets a sub-template (TemplateTestPart)
    because it is a component of Device.
    """
    return SchemaRoot(
        generics=[core_object_template, core_object_component_template],
        nodes=[
            NodeSchema(
                name="Device",
                namespace="Test",
                default_filter="name__value",
                display_labels=["name__value"],
                branch=BranchSupportType.AWARE,
                generate_template=True,
                attributes=[
                    AttributeSchema(name="name", kind="Text", unique=True),
                    AttributeSchema(name="description", kind="Text", optional=True),
                ],
                relationships=[
                    RelationshipSchema(
                        name="parts",
                        peer="TestPart",
                        kind=RelationshipKind.COMPONENT,
                        optional=True,
                        cardinality=RelationshipCardinality.MANY,
                        identifier="device__parts",
                    ),
                ],
            ),
            NodeSchema(
                name="Part",
                namespace="Test",
                default_filter="name__value",
                display_labels=["name__value"],
                branch=BranchSupportType.AWARE,
                # generate_template=False (default) — sub-template via Component relationship
                attributes=[
                    AttributeSchema(name="name", kind="Text", unique=True),
                    AttributeSchema(name="serial_number", kind="Text", optional=True, read_only=part_serial_read_only),
                ],
                relationships=[
                    RelationshipSchema(
                        name="device",
                        peer="TestDevice",
                        kind=RelationshipKind.PARENT,
                        optional=False,
                        cardinality=RelationshipCardinality.ONE,
                        identifier="device__parts",
                    ),
                ],
            ),
        ],
    )


@pytest.fixture
async def device_part_schema_subtemplate_read_only_serial(
    db: InfrahubDatabase, default_branch: Branch, node_group_schema: None, data_schema: None
) -> SchemaBranch:
    """Device/Part schema where Part.serial_number is read_only (no template support).

    TemplateTestPart nodes exist as sub-templates but won't have serial_number.
    """
    return registry.schema.register_schema(
        schema=_device_part_schema_root(part_serial_read_only=True),
        branch=default_branch.name,
    )


async def test_migration_enable_support_on_subtemplate(
    db: InfrahubDatabase,
    default_branch: Branch,
    device_part_schema_subtemplate_read_only_serial: SchemaBranch,
) -> None:
    """Test that enabling template support adds attributes to sub-template nodes.

    Sub-templates are templates for schemas where generate_template=False, but
    template nodes exist because the schema is a Component of a schema with
    generate_template=True.

    This is a regression test: the migration checks new_schema.generate_template
    which is False for sub-templates, causing the migration to be silently skipped.
    """
    # Create a device template (required as parent for the part sub-template)
    template_device = await Node.init(db=db, schema="TemplateTestDevice", branch=default_branch)
    await template_device.new(db=db, template_name="Template Device 1")
    await template_device.save(db=db)

    # Create sub-template node — serial_number is read_only so won't be on the template
    template_part = await Node.init(db=db, schema="TemplateTestPart", branch=default_branch)
    await template_part.new(db=db, template_name="Template Part Sub", device=template_device)
    await template_part.save(db=db)

    # Verify serial_number is NOT on the template node
    with pytest.raises(ValueError):
        template_part.get_attribute(name="serial_number")

    # Set up migration: read_only=True -> read_only=False on TestPart.serial_number
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_part_schema = schema.get(name="TestPart")
    prev_attr = prev_part_schema.get_attribute(name="serial_number")
    prev_attr.id = str(uuid.uuid4())

    candidate_schema = schema.duplicate()
    new_part_schema = candidate_schema.get(name="TestPart")
    new_attr = new_part_schema.get_attribute(name="serial_number")
    new_attr.id = prev_attr.id
    new_attr.read_only = False
    candidate_schema.set(name="TestPart", schema=new_part_schema)

    migration = AttributeSupportsGeneratedSchemaMigration(
        previous_node_schema=prev_part_schema,
        new_node_schema=new_part_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPart", field_name="serial_number"),
    )

    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not execution_result.errors

    # Verify the serial_number attribute was added to the sub-template node
    await assert_attribute_path_status(
        db=db,
        node_label="TemplateTestPart",
        attr_name="serial_number",
        branch_name=default_branch.name,
        expected_status="active",
    )


async def test_migration_edge_timestamps(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
    car_profile1_main: Node,
    car_template1_main: Node,
) -> None:
    """Verify edges created/modified during migration use the 'at' timestamp."""
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")
    prev_attr = prev_car_schema.get_attribute(name="nbr_seats")
    prev_attr.id = str(uuid.uuid4())

    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    new_attr = new_car_schema.get_attribute(name="nbr_seats")
    new_attr.id = prev_attr.id
    new_attr.read_only = True

    snapshotter = DbSnapshotter(db)
    before_snapshot = await snapshotter.snapshot()

    at = Timestamp()
    at_str = at.to_string()

    migration = AttributeSupportsGeneratedSchemaMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="nbr_seats"),
    )
    execution_result = await migration.execute(migration_input=MigrationInput(db=db, at=at), branch=default_branch)
    assert not execution_result.errors

    after_snapshot = await snapshotter.snapshot()
    assert_edge_timestamps(before_snapshot, after_snapshot, at_str)
