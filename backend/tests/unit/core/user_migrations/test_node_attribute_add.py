import uuid

import pytest

from infrahub.core.migrations.node_attribute_add import NodeAttributeAddMigration, NodeAttributeAddMigrationQuery01
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
async def init_database(db: InfrahubDatabase):
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


@pytest.mark.neo4j
async def test_query01(db: InfrahubDatabase, default_branch, init_database, schema_aware):
    node = schema_aware

    assert await count_nodes(db=db, label="TestCar") == 5
    assert await count_nodes(db=db, label="Attribute") == 0

    migration = NodeAttributeAddMigration(node=node, attribute=node.attributes[0])
    query = await NodeAttributeAddMigrationQuery01.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)

    assert await count_nodes(db=db, label="TestCar") == 5
    assert await count_nodes(db=db, label="Attribute") == 5

    # Re-execute the query once to ensure that it won't recreate the attribute twice
    query = await NodeAttributeAddMigrationQuery01.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)

    assert await count_nodes(db=db, label="TestCar") == 5
    assert await count_nodes(db=db, label="Attribute") == 5


@pytest.mark.neo4j
async def test_migration(db: InfrahubDatabase, default_branch, init_database, schema_aware):
    node = schema_aware
    migration = NodeAttributeAddMigration(node=node, attribute=node.attributes[0])

    assert await count_nodes(db=db, label="TestCar") == 5
    assert await count_nodes(db=db, label="Attribute") == 0

    execution_result = await migration.execute(db=db, branch=default_branch)
    assert not execution_result.errors

    assert await count_nodes(db=db, label="TestCar") == 5
    assert await count_nodes(db=db, label="Attribute") == 5
