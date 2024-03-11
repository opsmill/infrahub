from infrahub_sdk import UUIDT, InfrahubClient

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SchemaPathType
from infrahub.core.migrations.schema.node_remove import (
    NodeRemoveMigration,
    NodeRemoveMigrationQueryIn,
    NodeRemoveMigrationQueryOut,
)
from infrahub.core.path import SchemaPath
from infrahub.core.utils import count_nodes, count_relationships
from infrahub.database import InfrahubDatabase
from infrahub.message_bus import Meta
from infrahub.message_bus.messages import SchemaMigrationPath, SchemaMigrationPathResponse
from infrahub.services import InfrahubServices


async def test_query_out_default_branch(db: InfrahubDatabase, default_branch: Branch, car_accord_main, car_camry_main):
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    candidate_schema = schema.duplicate()
    candidate_schema.delete(name="TestCar")

    assert await count_nodes(db=db, label="TestCar") == 2

    count_rels = await count_relationships(db=db)

    migration = NodeRemoveMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=None,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestCar"),
    )
    query = await NodeRemoveMigrationQueryOut.init(db=db, branch=default_branch, migration=migration)

    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 2

    # we expect 7 new relationships per TestCar, 14 TOTAL
    # 5 attributes, 1 relationship & 1 for the root node
    assert await count_relationships(db=db) == count_rels + 14
    assert await count_nodes(db=db, label="TestCar") == 2

    # Re-execute the query once to ensure that it won't change anything
    query = await NodeRemoveMigrationQueryOut.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 0
    assert await count_relationships(db=db) == count_rels + 14
    assert await count_nodes(db=db, label="TestCar") == 2


async def test_query_in_default_branch(db: InfrahubDatabase, default_branch: Branch, car_accord_main, car_camry_main):
    """This test is a bit silly for now because there is nothing to migrate but it least we validate that the generated query is valid"""

    schema = registry.schema.get_schema_branch(name=default_branch.name)
    candidate_schema = schema.duplicate()
    candidate_schema.delete(name="TestCar")

    assert await count_nodes(db=db, label="TestCar") == 2

    count_rels = await count_relationships(db=db)

    migration = NodeRemoveMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=None,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestCar"),
    )
    query = await NodeRemoveMigrationQueryIn.init(db=db, branch=default_branch, migration=migration)

    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 0

    # we expect 0 new relationships because there is no inbound relationships defined currently
    assert await count_relationships(db=db) == count_rels + 0
    assert await count_nodes(db=db, label="TestCar") == 2

    # Re-execute the query once to ensure that it won't change anything
    query = await NodeRemoveMigrationQueryIn.init(db=db, branch=default_branch, migration=migration)
    await query.execute(db=db)
    assert query.get_nbr_migrations_executed() == 0
    assert await count_relationships(db=db) == count_rels + 0
    assert await count_nodes(db=db, label="TestCar") == 2


async def test_migration(db: InfrahubDatabase, default_branch: Branch, car_accord_main, car_camry_main):
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    candidate_schema = schema.duplicate()
    candidate_schema.delete(name="TestCar")

    assert await count_nodes(db=db, label="TestCar") == 2

    count_rels = await count_relationships(db=db)

    migration = NodeRemoveMigration(
        previous_node_schema=schema.get(name="TestCar"),
        new_node_schema=None,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestCar"),
    )

    execution_result = await migration.execute(db=db, branch=default_branch)
    assert not execution_result.errors
    assert execution_result.nbr_migrations_executed == 2
    assert await count_relationships(db=db) == count_rels + 14
    assert await count_nodes(db=db, label="TestCar") == 2


async def test_rpc(db: InfrahubDatabase, default_branch: Branch, car_accord_main, car_camry_main, helper):
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    candidate_schema = schema.duplicate()
    candidate_schema.delete(name="TestCar")

    correlation_id = str(UUIDT())
    message = SchemaMigrationPath(
        migration_name="node.remove",
        new_node_schema=None,
        previous_node_schema=schema.get(name="TestCar"),
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestCar"),
        branch=default_branch,
        meta=Meta(reply_to="ci-testing", correlation_id=correlation_id),
    )

    bus_simulator = helper.get_message_bus_simulator()
    service = InfrahubServices(message_bus=bus_simulator, client=InfrahubClient(), database=db)
    bus_simulator.service = service

    assert await count_nodes(db=db, label="TestCar") == 2

    response = await service.message_bus.rpc(message=message, response_class=SchemaMigrationPathResponse)
    assert response.passed
    assert not response.data.errors
    assert response.data.nbr_migrations_executed == 2

    assert await count_nodes(db=db, label="TestCar") == 2
