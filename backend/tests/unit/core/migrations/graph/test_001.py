from infrahub_sdk import UUIDT

from infrahub.core.migrations.graph import Migration001
from infrahub.database import InfrahubDatabase


async def test_migration_001_no_version(db: InfrahubDatabase, reset_registry, delete_all_nodes_in_db):
    query_init_root = """
    CREATE (root:Root { uuid: "%(uuid)s", default_branch: "main" })
    RETURN root
    """ % {"uuid": str(UUIDT().new())}
    await db.execute_query(query=query_init_root)

    migration = Migration001()
    execution_result = await migration.execute(db=db)
    assert not execution_result.errors

    validation_result = await migration.validate_migration(db=db)
    assert not validation_result.errors


async def test_migration_001_initial_version(db: InfrahubDatabase, reset_registry, delete_all_nodes_in_db):
    query_init_root = """
    CREATE (root:Root { uuid: "%(uuid)s", graph_version: 0, default_branch: "main" })
    RETURN root
    """ % {"uuid": str(UUIDT().new())}
    await db.execute_query(query=query_init_root)

    migration = Migration001()
    execution_result = await migration.execute(db=db)
    assert not execution_result.errors

    validation_result = await migration.validate_migration(db=db)
    assert not validation_result.errors


async def test_migration_001_validate(db: InfrahubDatabase, reset_registry, delete_all_nodes_in_db):
    root_id = str(UUIDT().new())

    query_init_root = """
    CREATE (root:Root { uuid: "%(uuid)s", graph_version: 0, default_branch: "main" })
    RETURN root
    """ % {"uuid": root_id}
    await db.execute_query(query=query_init_root)

    migration = Migration001()
    execution_result = await migration.execute(db=db)
    assert not execution_result.errors

    query_init_root = """
    MATCH (root:Root { uuid: "%(uuid)s" })
    SET root.graph_version = 0
    RETURN root
    """ % {"uuid": root_id}
    await db.execute_query(query=query_init_root)

    validation_result = await migration.validate_migration(db=db)
    assert not validation_result.success
    assert "The version of the graph should be 1, found 0 instead." in validation_result.errors
