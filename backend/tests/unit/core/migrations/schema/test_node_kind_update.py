from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SchemaPathType
from infrahub.core.migrations.schema.node_kind_update import (
    NodeKindUpdateMigration,
    NodeKindUpdateMigrationQuery01,
)
from infrahub.core.path import SchemaPath
from infrahub.core.utils import count_nodes, count_relationships
from infrahub.database import InfrahubDatabase


async def test_query_default_branch(db: InfrahubDatabase, default_branch: Branch, car_accord_main, car_camry_main):
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    candidate_schema = schema.duplicate()
    car_schema = candidate_schema.get(name="TestCar")
    candidate_schema.delete(name="TestCar")
    car_schema.name = "NewCar"
    car_schema.namespace = "Test2"
    candidate_schema.set(name="Test2NewCar", schema=car_schema)
    assert car_schema.kind == "Test2NewCar"

    assert await count_nodes(db=db, label="TestCar") == 2
    assert await count_nodes(db=db, label="Test2NewCar") == 0

    count_rels = await count_relationships(db=db)

    migration = NodeKindUpdateMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="Test2NewCar", field_name="namespace"),
    )
    query = await NodeKindUpdateMigrationQuery01.init(db=db, branch=default_branch, migration=migration)
    # print(query.get_query(var=True, inline=True))
    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 2

    # we expect 14 new relationships per TestCar, 28 TOTAL
    # 2 x 5 attributes = 10
    # 2 x 1 relationship = 2
    # 2 for the root node = 2
    assert await count_relationships(db=db) == count_rels + 28
    assert await count_nodes(db=db, label="TestCar") == 2
    assert await count_nodes(db=db, label="Test2NewCar") == 2

    # Re-execute the query once to ensure that it won't change anything
    query = await NodeKindUpdateMigrationQuery01.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 0
    assert await count_relationships(db=db) == count_rels + 28
    assert await count_nodes(db=db, label="TestCar") == 2
    assert await count_nodes(db=db, label="Test2NewCar") == 2


async def test_migration(db: InfrahubDatabase, default_branch: Branch, car_accord_main, car_camry_main):
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    candidate_schema = schema.duplicate()
    car_schema = candidate_schema.get(name="TestCar")
    candidate_schema.delete(name="TestCar")
    car_schema.name = "NewCar"
    car_schema.namespace = "Test2"
    candidate_schema.set(name="Test2NewCar", schema=car_schema)
    assert car_schema.kind == "Test2NewCar"

    assert await count_nodes(db=db, label="TestCar") == 2
    assert await count_nodes(db=db, label="Test2NewCar") == 0

    count_rels = await count_relationships(db=db)

    migration = NodeKindUpdateMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="namespace"),
    )

    execution_result = await migration.execute(db=db, branch=default_branch)
    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 2
    assert await count_relationships(db=db) == count_rels + 28
    assert await count_nodes(db=db, label="TestCar") == 2
    assert await count_nodes(db=db, label="Test2NewCar") == 2
