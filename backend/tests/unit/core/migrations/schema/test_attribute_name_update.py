import uuid

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SchemaPathType
from infrahub.core.initialization import (
    create_branch,
)
from infrahub.core.migrations.schema.attribute_name_update import (
    AttributeNameUpdateMigration,
    AttributeNameUpdateMigrationQuery01,
)
from infrahub.core.path import SchemaPath
from infrahub.core.utils import count_nodes, count_relationships
from infrahub.database import InfrahubDatabase


async def test_query_default_branch(db: InfrahubDatabase, default_branch: Branch, car_accord_main, car_camry_main):
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

    assert query.get_nbr_migrations_executed() == 2

    # We expect 8 more relationships because there are 2 attributes with 4 relationships each
    assert await count_relationships(db=db) == count_rels + 8
    assert await count_nodes(db=db, label="Attribute") == count_attr_node + 2

    # Re-execute the query once to ensure that it won't change anything
    query = await AttributeNameUpdateMigrationQuery01.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 0

    assert await count_nodes(db=db, label="Attribute") == count_attr_node + 2
    assert await count_relationships(db=db) == count_rels + 8


async def test_query_branch1(db: InfrahubDatabase, default_branch: Branch, car_accord_main, car_camry_main):
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
    assert query.get_nbr_migrations_executed() == 2

    # We expect 16 more relationships because there are 2 attributes with 4 relationships each
    assert await count_relationships(db=db) == count_rels + 16
    assert await count_nodes(db=db, label="Attribute") == count_attr_node + 2

    # Re-execute the query once to ensure that it won't change anything
    query = await AttributeNameUpdateMigrationQuery01.init(db=db, branch=branch1, migration=migration)
    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 0

    assert await count_nodes(db=db, label="Attribute") == count_attr_node + 2
    assert await count_relationships(db=db) == count_rels + 16


async def test_migration(db: InfrahubDatabase, default_branch: Branch, car_accord_main, car_camry_main):
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

    execution_result = await migration.execute(db=db, branch=default_branch)
    assert not execution_result.errors

    assert execution_result.nbr_migrations_executed == 2

    assert await count_nodes(db=db, label="Attribute") == count_attr_node + 2
    assert await count_relationships(db=db) == count_rels + 8
