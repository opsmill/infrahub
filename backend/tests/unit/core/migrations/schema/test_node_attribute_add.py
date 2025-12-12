import uuid

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import HashableModelState, SchemaPathType
from infrahub.core.migrations.schema.node_attribute_add import (
    NodeAttributeAddMigration,
    NodeAttributeAddMigrationQuery01,
)
from infrahub.core.migrations.schema.node_attribute_remove import (
    NodeAttributeRemoveMigration,
    NodeAttributeRemoveMigrationQuery01,
)
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import NodeSchema
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import count_nodes
from infrahub.database import InfrahubDatabase


@pytest.fixture
async def schema_aware():
    SCHEMA = {
        "name": "Car",
        "namespace": "Test",
        "branch": "aware",
        "attributes": [
            {"name": "nbr_doors", "kind": "Number", "branch": "aware"},
        ],
    }

    node = NodeSchema(**SCHEMA)
    return node


@pytest.fixture
async def init_database(db: InfrahubDatabase) -> None:
    params = {
        "nodes": [],
        "rel_props": {"branch": "main", "branch_level": "1", "status": "active", "from": Timestamp().to_string()},
    }

    for _ in range(5):
        node_param = {
            "uuid": str(uuid.uuid4()),
            "kind": "TestCar",
            "namespace": "Test",
            "branch_support": "aware",
        }
        params["nodes"].append(node_param)

    query_init_root = """
    MATCH (root:Root)
    FOREACH ( node IN $nodes |
        CREATE (n:Node:TestCar { uuid: node.uuid, kind: node.kind, namespace: node.namespace, branch_support: node.branch_support })
        CREATE (n)-[r:IS_PART_OF $rel_props ]->(root)
    )
    RETURN root
    """ % {}
    await db.execute_query(query=query_init_root, params=params)


async def test_query01(db: InfrahubDatabase, default_branch, init_database, schema_aware) -> None:
    node = schema_aware

    assert await count_nodes(db=db, label="TestCar") == 5
    assert await count_nodes(db=db, label="Attribute") == 0

    migration = NodeAttributeAddMigration(
        new_node_schema=node,
        previous_node_schema=node,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="nbr_doors"),
    )
    query = await NodeAttributeAddMigrationQuery01.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)

    assert query.get_nbr_migrations_executed() == 5
    assert await count_nodes(db=db, label="TestCar") == 5
    assert await count_nodes(db=db, label="Attribute") == 5

    # Re-execute the query once to ensure that it won't recreate the attribute twice
    query = await NodeAttributeAddMigrationQuery01.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)

    assert query.get_nbr_migrations_executed() == 0
    assert await count_nodes(db=db, label="TestCar") == 5
    assert await count_nodes(db=db, label="Attribute") == 5


async def test_query01_re_add(db: InfrahubDatabase, default_branch: Branch, car_accord_main, car_camry_main) -> None:
    schema = registry.schema.get_schema_branch(name=default_branch.name)

    assert await count_nodes(db=db, label="TestCar") == 2
    assert await count_nodes(db=db, label="Attribute") == 22

    # ------------------------------------------
    # Delete the attribute Color
    # ------------------------------------------
    candidate_schema = schema.duplicate()
    car_schema = candidate_schema.get_node(name="TestCar")
    attr = car_schema.get_attribute(name="color")
    attr.state = HashableModelState.ABSENT

    migration_remove = NodeAttributeRemoveMigration(
        previous_node_schema=schema.get_node(name="TestCar"),
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="color"),
    )
    query = await NodeAttributeRemoveMigrationQuery01.init(db=db, branch=default_branch, migration=migration_remove)
    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 2

    # ------------------------------------------
    # Add the attribute Color back
    # ------------------------------------------
    migration_add = NodeAttributeAddMigration(
        new_node_schema=schema.get_node(name="TestCar"),
        previous_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="color"),
    )
    query = await NodeAttributeAddMigrationQuery01.init(db=db, branch=default_branch, migration=migration_add)
    await query.execute(db=db)

    assert query.get_nbr_migrations_executed() == 2

    assert await count_nodes(db=db, label="TestCar") == 2
    assert await count_nodes(db=db, label="Attribute") == 24

    # Re-execute the query once to ensure that it won't recreate the attribute twice
    query = await NodeAttributeAddMigrationQuery01.init(db=db, branch=default_branch, migration=migration_add)
    await query.execute(db=db)

    assert query.get_nbr_migrations_executed() == 0
    assert await count_nodes(db=db, label="TestCar") == 2
    assert await count_nodes(db=db, label="Attribute") == 24


async def test_migration(db: InfrahubDatabase, default_branch, init_database, schema_aware) -> None:
    node = schema_aware
    migration = NodeAttributeAddMigration(
        new_node_schema=node,
        previous_node_schema=node,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="nbr_doors"),
    )

    assert await count_nodes(db=db, label="TestCar") == 5
    assert await count_nodes(db=db, label="Attribute") == 0

    execution_result = await migration.execute(db=db, branch=default_branch)
    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 5
    assert await count_nodes(db=db, label="TestCar") == 5
    assert await count_nodes(db=db, label="Attribute") == 5


async def test_migration_with_user_id(db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node) -> None:
    """Test that the user_id passed to migration.execute() is correctly set on the created attribute's metadata."""
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    car_schema = schema.get_node(name="TestCar")

    # Remove the color attribute first so we can re-add it with a specific user_id
    remove_migration = NodeAttributeRemoveMigration(
        previous_node_schema=car_schema,
        new_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="color"),
    )
    await remove_migration.execute(db=db, branch=default_branch)

    test_user_id = "test-migration-user"
    migration = NodeAttributeAddMigration(
        new_node_schema=car_schema,
        previous_node_schema=car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="color"),
    )
    migration_time = Timestamp()
    execution_result = await migration.execute(db=db, branch=default_branch, at=migration_time, user_id=test_user_id)

    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 1

    # Verify directly via Cypher that from_user_id is set on the edges
    query = """
    MATCH (n:TestCar {uuid: $car_uuid})-[:HAS_ATTRIBUTE]->(attr:Attribute {name: "color"})
    MATCH (attr)-[r {status: "active", from: $migration_time}]-()
    RETURN r.from_user_id as from_user_id
    """
    results = await db.execute_query(
        query=query,
        params={"car_uuid": car_accord_main.id, "migration_time": migration_time.to_string()},
    )
    assert len(results) > 0, "Expected at least one active edge on added attribute"
    for record in results:
        assert record["from_user_id"] == test_user_id
