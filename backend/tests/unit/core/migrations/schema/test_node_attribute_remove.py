from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import HashableModelState, SchemaPathType
from infrahub.core.migrations.schema.node_attribute_remove import (
    NodeAttributeRemoveMigration,
    NodeAttributeRemoveMigrationQuery01,
)
from infrahub.core.path import SchemaPath
from infrahub.core.utils import count_nodes, count_relationships
from infrahub.database import InfrahubDatabase


async def test_query_default_branch(db: InfrahubDatabase, default_branch: Branch, car_accord_main, car_camry_main):
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    candidate_schema = schema.duplicate()
    car_schema = candidate_schema.get(name="TestCar")
    attr = car_schema.get_attribute(name="color")
    attr.state = HashableModelState.ABSENT

    count_attr_node = await count_nodes(db=db, label="Attribute")
    count_rels = await count_relationships(db=db)

    migration = NodeAttributeRemoveMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="color"),
    )
    query = await NodeAttributeRemoveMigrationQuery01.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 2

    # We expect 8 more relationships because there are 2 attributes with 4 relationships each
    assert await count_relationships(db=db) == count_rels + 8
    assert await count_nodes(db=db, label="Attribute") == count_attr_node

    # Re-execute the query once to ensure that it won't change anything
    query = await NodeAttributeRemoveMigrationQuery01.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 0
    assert await count_nodes(db=db, label="Attribute") == count_attr_node
    assert await count_relationships(db=db) == count_rels + 8


async def test_migration(db: InfrahubDatabase, default_branch: Branch, car_accord_main, car_camry_main):
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    candidate_schema = schema.duplicate()
    car_schema = candidate_schema.get(name="TestCar")
    attr = car_schema.get_attribute(name="color")
    attr.state = HashableModelState.ABSENT

    count_attr_node = await count_nodes(db=db, label="Attribute")
    count_rels = await count_relationships(db=db)

    migration = NodeAttributeRemoveMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="color"),
    )

    execution_result = await migration.execute(db=db, branch=default_branch)
    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 2
    assert await count_nodes(db=db, label="Attribute") == count_attr_node
    assert await count_relationships(db=db) == count_rels + 8
