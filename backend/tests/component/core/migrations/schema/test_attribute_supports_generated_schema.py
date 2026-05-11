import uuid

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import RelationshipCardinality, RelationshipKind, SchemaPathType
from infrahub.core.migrations.schema.attribute_supports_generated_schema import (
    AttributeSupportsGeneratedSchemaMigration,
)
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.definitions.core.template import core_object_component_template, core_object_template
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.db_snapshot import DbSnapshotter
from tests.helpers.db_validation import assert_attribute_path_status
from tests.helpers.edge_timestamps import assert_edge_timestamps


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
async def car_person_schema_unique_seats(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_unregistered: SchemaRoot
) -> SchemaBranch:
    registry.schema.register_schema(schema=SchemaRoot(generics=[core_object_template]), branch=default_branch.name)
    for node in car_person_schema_unregistered.nodes:
        node.generate_template = True
    car_node = next(n for n in car_person_schema_unregistered.nodes if n.name == "Car")
    nbr_seats_attr = next(a for a in car_node.attributes if a.name == "nbr_seats")
    nbr_seats_attr.unique = True
    return registry.schema.register_schema(schema=car_person_schema_unregistered, branch=default_branch.name)


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


_PART = NodeSchema(
    name="Part",
    namespace="Test",
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
        AttributeSchema(name="serial_number", kind="Text", optional=True),
    ],
)

_DEVICE = NodeSchema(
    name="Device",
    namespace="Test",
    generate_template=True,
    attributes=[AttributeSchema(name="hostname", kind="Text", unique=True)],
    relationships=[
        RelationshipSchema(
            name="parts",
            peer="TestPart",
            kind=RelationshipKind.COMPONENT,
            cardinality=RelationshipCardinality.MANY,
            optional=True,
        )
    ],
)


@pytest.fixture
async def device_part_schema_read_only_serial(
    db: InfrahubDatabase, default_branch: Branch, node_group_schema: None, data_schema: None
) -> SchemaBranch:
    """TestDevice (generate_template=True) has COMPONENT TestPart (generate_template=False).
    serial_number starts read_only=True so it is NOT on template instances."""
    part = _PART.duplicate()
    part.get_attribute("serial_number").read_only = True
    registry.schema.register_schema(
        schema=SchemaRoot(generics=[core_object_template, core_object_component_template]),
        branch=default_branch.name,
    )
    return registry.schema.register_schema(schema=SchemaRoot(nodes=[_DEVICE, part]), branch=default_branch.name)


@pytest.fixture
async def device_part_schema(
    db: InfrahubDatabase, default_branch: Branch, node_group_schema: None, data_schema: None
) -> SchemaBranch:
    """TestDevice (generate_template=True) has COMPONENT TestPart (generate_template=False).
    serial_number starts read_only=False so it IS on template instances.
    """
    registry.schema.register_schema(
        schema=SchemaRoot(generics=[core_object_template, core_object_component_template]),
        branch=default_branch.name,
    )
    return registry.schema.register_schema(schema=SchemaRoot(nodes=[_DEVICE, _PART]), branch=default_branch.name)


async def test_migration_enable_support_sub_template(
    db: InfrahubDatabase,
    default_branch: Branch,
    device_part_schema_read_only_serial: SchemaBranch,
) -> None:
    """Enabling read_only→False on a sub-template schema adds the attribute to existing TemplateTestPart instances."""
    template_part = await Node.init(db=db, schema="TemplateTestPart", branch=default_branch)
    await template_part.new(db=db, template_name="Template Part 1")
    await template_part.save(db=db)

    with pytest.raises(ValueError):
        template_part.get_attribute(name="serial_number")

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

    await assert_attribute_path_status(
        db=db,
        node_label="TemplateTestPart",
        attr_name="serial_number",
        branch_name=default_branch.name,
        expected_status="active",
    )


async def test_migration_disable_support_sub_template(
    db: InfrahubDatabase,
    default_branch: Branch,
    device_part_schema: SchemaBranch,
) -> None:
    """Disabling read_only→True on a sub-template schema removes the attribute from existing TemplateTestPart instances."""
    template_part = await Node.init(db=db, schema="TemplateTestPart", branch=default_branch)
    await template_part.new(db=db, template_name="Template Part 1", serial_number="SN-12345")
    await template_part.save(db=db)

    await assert_attribute_path_status(
        db=db,
        node_label="TemplateTestPart",
        attr_name="serial_number",
        branch_name=default_branch.name,
        expected_status="active",
    )

    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_part_schema = schema.get(name="TestPart")
    prev_attr = prev_part_schema.get_attribute(name="serial_number")
    prev_attr.id = str(uuid.uuid4())

    candidate_schema = schema.duplicate()
    new_part_schema = candidate_schema.get(name="TestPart")
    new_attr = new_part_schema.get_attribute(name="serial_number")
    new_attr.id = prev_attr.id
    new_attr.read_only = True
    candidate_schema.set(name="TestPart", schema=new_part_schema)

    migration = AttributeSupportsGeneratedSchemaMigration(
        previous_node_schema=prev_part_schema,
        new_node_schema=new_part_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPart", field_name="serial_number"),
    )

    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not execution_result.errors

    await assert_attribute_path_status(
        db=db,
        node_label="TemplateTestPart",
        attr_name="serial_number",
        branch_name=default_branch.name,
        expected_status="deleted",
    )


async def test_migration_unique_enable_support(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema_unique_seats: SchemaBranch,
) -> None:
    """Test that unique: True → False adds the attribute to profile and template nodes."""
    profile = await Node.init(db=db, schema="ProfileTestCar", branch=default_branch)
    await profile.new(db=db, profile_name="car-profile1", is_electric=False)
    await profile.save(db=db)

    template_person = await Node.init(db=db, schema="TemplateTestPerson", branch=default_branch)
    await template_person.new(db=db, template_name="Template Person 1")
    await template_person.save(db=db)

    template = await Node.init(db=db, schema="TemplateTestCar", branch=default_branch)
    await template.new(db=db, template_name="Template Car 1", is_electric=False, owner=template_person)
    await template.save(db=db)

    with pytest.raises(ValueError):
        profile.get_attribute(name="nbr_seats")
    with pytest.raises(ValueError):
        template.get_attribute(name="nbr_seats")

    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")
    prev_attr = prev_car_schema.get_attribute(name="nbr_seats")
    prev_attr.id = str(uuid.uuid4())

    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    new_attr = new_car_schema.get_attribute(name="nbr_seats")
    new_attr.id = prev_attr.id
    new_attr.unique = False
    if new_car_schema.uniqueness_constraints:
        new_car_schema.uniqueness_constraints = [["name__value"]]
    candidate_schema.set(name="TestCar", schema=new_car_schema)

    migration = AttributeSupportsGeneratedSchemaMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="nbr_seats"),
    )

    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not execution_result.errors

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


@pytest.fixture
async def device_part_schema_unique_serial(
    db: InfrahubDatabase, default_branch: Branch, node_group_schema: None, data_schema: None
) -> SchemaBranch:
    """TestDevice (generate_template=True) has COMPONENT TestPart (generate_template=False).
    serial_number starts unique=True so it is NOT on template instances."""
    part = _PART.duplicate()
    part.get_attribute("serial_number").unique = True
    registry.schema.register_schema(
        schema=SchemaRoot(generics=[core_object_template, core_object_component_template]),
        branch=default_branch.name,
    )
    return registry.schema.register_schema(schema=SchemaRoot(nodes=[_DEVICE, part]), branch=default_branch.name)


async def test_migration_unique_enable_support_sub_template(
    db: InfrahubDatabase,
    default_branch: Branch,
    device_part_schema_unique_serial: SchemaBranch,
) -> None:
    """Test that unique: True → False on a sub-template schema adds the attribute to existing TemplateTestPart instances."""
    template_part = await Node.init(db=db, schema="TemplateTestPart", branch=default_branch)
    await template_part.new(db=db, template_name="Template Part 1")
    await template_part.save(db=db)

    with pytest.raises(ValueError):
        template_part.get_attribute(name="serial_number")

    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_part_schema = schema.get(name="TestPart")
    prev_attr = prev_part_schema.get_attribute(name="serial_number")
    prev_attr.id = str(uuid.uuid4())

    candidate_schema = schema.duplicate()
    new_part_schema = candidate_schema.get(name="TestPart")
    new_attr = new_part_schema.get_attribute(name="serial_number")
    new_attr.id = prev_attr.id
    new_attr.unique = False
    candidate_schema.set(name="TestPart", schema=new_part_schema)

    migration = AttributeSupportsGeneratedSchemaMigration(
        previous_node_schema=prev_part_schema,
        new_node_schema=new_part_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPart", field_name="serial_number"),
    )

    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not execution_result.errors

    await assert_attribute_path_status(
        db=db,
        node_label="TemplateTestPart",
        attr_name="serial_number",
        branch_name=default_branch.name,
        expected_status="active",
    )


async def test_migration_unique_disable_support(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
    car_profile1_main: Node,
    car_template1_main: Node,
) -> None:
    """Test that unique: False → True removes the attribute from profile and template nodes."""
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

    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")
    prev_attr = prev_car_schema.get_attribute(name="nbr_seats")
    prev_attr.id = str(uuid.uuid4())

    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    new_attr = new_car_schema.get_attribute(name="nbr_seats")
    new_attr.id = prev_attr.id
    new_attr.unique = True

    migration = AttributeSupportsGeneratedSchemaMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="nbr_seats"),
    )

    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=default_branch)
    assert not execution_result.errors

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


async def test_migration_no_change_when_unique_unchanged(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_person_schema: SchemaBranch,
    car_profile1_main: Node,
    car_template1_main: Node,
) -> None:
    """Test that migration does nothing when unique does not change."""
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
