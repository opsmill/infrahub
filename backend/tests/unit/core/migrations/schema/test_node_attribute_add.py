import uuid

import pytest
from infrahub_sdk import InfrahubClient
from infrahub_sdk.uuidt import UUIDT

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
from infrahub.core.path import SchemaPath
from infrahub.core.schema import NodeSchema
from infrahub.core.timestamp import Timestamp
from infrahub.core.utils import count_nodes
from infrahub.database import InfrahubDatabase
from infrahub.message_bus import Meta
from infrahub.message_bus.messages import SchemaMigrationPath, SchemaMigrationPathResponse
from infrahub.services import InfrahubServices


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


async def test_query01(db: InfrahubDatabase, default_branch, init_database, schema_aware):
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


async def test_query01_re_add(db: InfrahubDatabase, default_branch: Branch, car_accord_main, car_camry_main):
    schema = registry.schema.get_schema_branch(name=default_branch.name)

    assert await count_nodes(db=db, label="TestCar") == 2
    assert await count_nodes(db=db, label="Attribute") == 14

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
    assert await count_nodes(db=db, label="Attribute") == 16

    # Re-execute the query once to ensure that it won't recreate the attribute twice
    query = await NodeAttributeAddMigrationQuery01.init(db=db, branch=default_branch, migration=migration_add)
    await query.execute(db=db)

    assert query.get_nbr_migrations_executed() == 0
    assert await count_nodes(db=db, label="TestCar") == 2
    assert await count_nodes(db=db, label="Attribute") == 16


async def test_migration(db: InfrahubDatabase, default_branch, init_database, schema_aware):
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


async def test_rpc(db: InfrahubDatabase, default_branch, init_database, schema_aware, helper):
    node = schema_aware
    correlation_id = str(UUIDT())
    message = SchemaMigrationPath(
        migration_name="node.attribute.add",
        new_node_schema=node,
        previous_node_schema=node,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestCar", field_name="nbr_doors"),
        branch=default_branch,
        meta=Meta(reply_to="ci-testing", correlation_id=correlation_id),
    )

    bus_simulator = helper.get_message_bus_simulator()
    service = InfrahubServices(message_bus=bus_simulator, client=InfrahubClient(), database=db)
    bus_simulator.service = service

    assert await count_nodes(db=db, label="TestCar") == 5
    assert await count_nodes(db=db, label="Attribute") == 0

    response = await service.message_bus.rpc(message=message, response_class=SchemaMigrationPathResponse)
    assert response.passed
    assert not response.data.errors

    assert await count_nodes(db=db, label="TestCar") == 5
    assert await count_nodes(db=db, label="Attribute") == 5
