import pytest

from infrahub.core.migrations.graph.m003_relationship_parent_optional import Migration003, Migration003Query01
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot, internal_schema
from infrahub.core.schema_manager import SchemaBranch
from infrahub.core.utils import count_relationships
from infrahub.database import InfrahubDatabase


@pytest.fixture
async def migration_003_data(db: InfrahubDatabase, reset_registry, default_branch, delete_all_nodes_in_db):
    #     # load the internal schema from
    schema = SchemaRoot(**internal_schema)
    schema_branch = SchemaBranch(cache={}, name="default_branch")
    schema_branch.load_schema(schema=schema)
    schema_branch.process()

    node_schema = schema_branch.get(name="SchemaNode")
    rel_schema = schema_branch.get(name="SchemaRelationship")

    node1 = await Node.init(db=db, schema=node_schema)
    await node1.new(db=db, name="Node", namespace="Test")
    await node1.save(db=db)

    rel1 = await Node.init(db=db, schema=rel_schema)
    await rel1.new(db=db, name="rel1", kind="Parent", peer="CoreNode", optional=True, node=node1)
    await rel1.save(db=db)

    rel2 = await Node.init(db=db, schema=rel_schema)
    await rel2.new(db=db, name="rel2", kind="Parent", peer="CoreNode", optional=False, node=node1)
    await rel2.save(db=db)


async def test_migration_003_query1(
    db: InfrahubDatabase, reset_registry, default_branch, delete_all_nodes_in_db, migration_003_data
):
    nbr_rels_before = await count_relationships(db=db)
    query = await Migration003Query01.init(db=db)
    await query.execute(db=db)
    assert query.num_of_results == 1

    query = await Migration003Query01.init(db=db)
    await query.execute(db=db)
    assert query.num_of_results == 0

    nbr_rels_after = await count_relationships(db=db)
    assert nbr_rels_after == nbr_rels_before + 1


async def test_migration_003(
    db: InfrahubDatabase, reset_registry, default_branch, delete_all_nodes_in_db, migration_003_data
):
    nbr_rels_before = await count_relationships(db=db)

    migration = Migration003()
    execution_result = await migration.execute(db=db)
    assert not execution_result.errors

    validation_result = await migration.validate_migration(db=db)
    assert not validation_result.errors

    nbr_rels_after = await count_relationships(db=db)
    assert nbr_rels_after == nbr_rels_before + 1


# async def test_migration_001_validate(db: InfrahubDatabase, reset_registry, delete_all_nodes_in_db):
#     root_id = str(UUIDT().new())

#     query_init_root = """
#     CREATE (root:Root { uuid: "%(uuid)s", graph_version: 0, default_branch: "main" })
#     RETURN root
#     """ % {"uuid": root_id}
#     await db.execute_query(query=query_init_root)

#     migration = Migration001()
#     execution_result = await migration.execute(db=db)
#     assert not execution_result.errors

#     query_init_root = """
#     MATCH (root:Root { uuid: "%(uuid)s" })
#     SET root.graph_version = 0
#     RETURN root
#     """ % {"uuid": root_id}
#     await db.execute_query(query=query_init_root)

#     validation_result = await migration.validate_migration(db=db)
#     assert not validation_result.success
#     assert "The version of the graph should be 1, found 0 instead." in validation_result.errors
