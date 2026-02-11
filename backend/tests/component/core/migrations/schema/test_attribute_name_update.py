import uuid

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SYSTEM_USER_ID, MetadataOptions, SchemaPathType
from infrahub.core.initialization import (
    create_branch,
)
from infrahub.core.manager import NodeManager
from infrahub.core.metadata.model import MetadataQueryOptions
from infrahub.core.migrations.schema.attribute_name_update import (
    AttributeNameUpdateMigration,
    AttributeNameUpdateMigrationQuery01,
)
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.definitions.core.template import core_object_template
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import count_nodes, count_relationships
from infrahub.database import InfrahubDatabase
from tests.db_snapshot import DbSnapshotter
from tests.helpers.edge_timestamps import assert_edge_timestamps


@pytest.fixture
async def car_person_schema(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema_unregistered: SchemaRoot
) -> SchemaBranch:
    registry.schema.register_schema(schema=SchemaRoot(generics=[core_object_template]), branch=default_branch.name)
    for node in car_person_schema_unregistered.nodes:
        node.generate_template = True
    return registry.schema.register_schema(schema=car_person_schema_unregistered, branch=default_branch.name)


async def test_query_default_branch(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main, car_camry_main, car_profile1_main
) -> None:
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")
    prev_attr = prev_car_schema.get_attribute(name="color")
    prev_attr.id = str(uuid.uuid4())
    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    new_attr = new_car_schema.get_attribute(name="color")
    new_attr.name = "new-color"
    new_attr.id = prev_attr.id

    count_attr_node = await count_nodes(db=db, label="Attribute")
    count_rels = await count_relationships(db=db)

    migration = AttributeNameUpdateMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="new-color"),
    )
    query = await AttributeNameUpdateMigrationQuery01.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)

    assert query.get_nbr_migrations_executed() == 3

    # We expect 9 more relationships because there are 3 attributes with 3 relationships each
    assert await count_relationships(db=db) == count_rels + 9
    assert await count_nodes(db=db, label="Attribute") == count_attr_node + 3

    # Re-execute the query once to ensure that it won't change anything
    query = await AttributeNameUpdateMigrationQuery01.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 0

    assert await count_nodes(db=db, label="Attribute") == count_attr_node + 3
    assert await count_relationships(db=db) == count_rels + 9


async def test_query_branch1(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main, car_camry_main, car_profile1_main
) -> None:
    branch1 = await create_branch(db=db, branch_name="branch1", isolated=True)

    schema = registry.schema.get_schema_branch(name=branch1.name)
    prev_car_schema = schema.get(name="TestCar")
    prev_attr = prev_car_schema.get_attribute(name="color")
    prev_attr.id = str(uuid.uuid4())
    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    new_attr = new_car_schema.get_attribute(name="color")
    new_attr.name = "new-color"
    new_attr.id = prev_attr.id

    count_attr_node = await count_nodes(db=db, label="Attribute")
    count_rels = await count_relationships(db=db)

    migration = AttributeNameUpdateMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="new-color"),
    )
    query = await AttributeNameUpdateMigrationQuery01.init(db=db, branch=branch1, migration=migration)

    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 3

    # We expect 18 more relationships because there are 3 attributes with 6 relationships each
    assert await count_relationships(db=db) == count_rels + 18
    assert await count_nodes(db=db, label="Attribute") == count_attr_node + 3

    # Re-execute the query once to ensure that it won't change anything
    query = await AttributeNameUpdateMigrationQuery01.init(db=db, branch=branch1, migration=migration)
    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 0

    assert await count_nodes(db=db, label="Attribute") == count_attr_node + 3
    assert await count_relationships(db=db) == count_rels + 18


async def test_migration(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main, car_camry_main, car_profile1_main
) -> None:
    # Create TemplateTestPerson nodes to use as owners for TemplateTestCar
    template_person1 = await Node.init(db=db, schema="TemplateTestPerson", branch=default_branch)
    await template_person1.new(db=db, template_name="Template Person 1")
    await template_person1.save(db=db)
    template_person2 = await Node.init(db=db, schema="TemplateTestPerson", branch=default_branch)
    await template_person2.new(db=db, template_name="Template Person 2")
    await template_person2.save(db=db)

    # Create 2 TemplateTestCar nodes so migration also covers templates
    template1 = await Node.init(db=db, schema="TemplateTestCar", branch=default_branch)
    await template1.new(db=db, template_name="Template Accord", color="#111111", owner=template_person1)
    await template1.save(db=db)
    template2 = await Node.init(db=db, schema="TemplateTestCar", branch=default_branch)
    await template2.new(db=db, template_name="Template Camry", color="#222222", owner=template_person2)
    await template2.save(db=db)

    schema = registry.schema.get_schema_branch(name=default_branch.name)
    prev_car_schema = schema.get(name="TestCar")
    prev_attr = prev_car_schema.get_attribute(name="color")
    prev_attr.id = str(uuid.uuid4())
    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    new_attr = new_car_schema.get_attribute(name="color")
    new_attr.name = "new-color"
    new_attr.id = prev_attr.id

    # 1. Snapshot before migration
    snapshotter = DbSnapshotter(db)
    before_snapshot = await snapshotter.snapshot()

    # 2. Count nodes and relationships before migration
    count_attr_node = await count_nodes(db=db, label="Attribute")
    count_rels = await count_relationships(db=db)

    # 3. Create explicit timestamp
    at = Timestamp()
    at_str = at.to_string()

    # 4. Execute migration
    migration = AttributeNameUpdateMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="new-color"),
    )
    execution_result = await migration.execute(migration_input=MigrationInput(db=db, at=at), branch=default_branch)
    assert not execution_result.errors
    # 2 TestCar + 1 ProfileTestCar + 2 TemplateTestCar = 5 migrations
    assert execution_result.nbr_migrations_executed == 5

    # 5. Validate nodes and relationships after migration
    # 5 new Attribute nodes (one per renamed attribute), 5 x 3 = 15 new relationships
    assert await count_nodes(db=db, label="Attribute") == count_attr_node + 5
    assert await count_relationships(db=db) == count_rels + 15

    # 6. Validate edge timestamps
    after_snapshot = await snapshotter.snapshot()
    assert_edge_timestamps(before_snapshot, after_snapshot, at_str)


async def test_migration_metadata(db: InfrahubDatabase, car_accord_main: Node, branch: Branch) -> None:
    """Test that metadata is set correctly when renaming an attribute."""
    schema = registry.schema.get_schema_branch(name=branch.name)
    prev_car_schema = schema.get(name="TestCar")
    prev_attr = prev_car_schema.get_attribute(name="color")
    prev_attr.id = str(uuid.uuid4())
    candidate_schema = schema.duplicate()
    new_car_schema = candidate_schema.get(name="TestCar")
    new_attr = new_car_schema.get_attribute(name="color")
    new_attr.name = "new_color"
    new_attr.id = prev_attr.id

    test_user_id = "test-metadata-user"
    migration_time = Timestamp()

    migration = AttributeNameUpdateMigration(
        previous_node_schema=prev_car_schema,
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="new_color"),
    )
    execution_result = await migration.execute(
        migration_input=MigrationInput(db=db, at=migration_time, user_id=test_user_id), branch=branch
    )
    assert not execution_result.errors

    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    car_schema = schema_branch.get(name="TestCar", duplicate=False)
    color_attr = car_schema.get_attribute(name="color")
    color_attr.name = "new_color"

    updated_car = await NodeManager.get_one(
        db=db,
        branch=branch,
        id=car_accord_main.id,
        include_metadata=MetadataQueryOptions(
            node_level=MetadataOptions.USER_TIMESTAMPS, attribute_level=MetadataOptions.USER_TIMESTAMPS
        ),
        fields={"new_color": True},
    )
    assert updated_car._get_created_at() < migration_time
    assert updated_car._get_created_by() == SYSTEM_USER_ID
    assert updated_car._get_updated_at() == migration_time
    assert updated_car._get_updated_by() == test_user_id

    new_attr = updated_car.new_color
    assert new_attr._get_created_at() == migration_time
    assert new_attr._get_created_by() == test_user_id
    assert new_attr._get_updated_at() == migration_time
    assert new_attr._get_updated_by() == test_user_id
