from infrahub.core.branch.models import Branch
from infrahub.core.migrations.graph.m075_add_attribute_ipaddress_index import (
    INDEX_TO_ADD,
    Migration075,
)
from infrahub.core.migrations.shared import MigrationInput
from infrahub.database import DatabaseType, InfrahubDatabase
from infrahub.database.neo4j import IndexManagerNeo4j


async def test_migration_075(
    db: InfrahubDatabase,
    reset_registry: None,
    default_branch: Branch,
    delete_all_nodes_in_db: None,
) -> None:
    if db.db_type is not DatabaseType.NEO4J:
        return

    index_manager = IndexManagerNeo4j(db=db)
    index_manager.init(nodes=[INDEX_TO_ADD], rels=[])
    # start from a known state without the AttributeIPAddress index
    await index_manager.drop()
    nbr_indexes_before = len(await index_manager.list())

    async with db.start_session() as dbs:
        migration = Migration075()
        execution_result = await migration.execute(migration_input=MigrationInput(db=dbs))
        assert not execution_result.errors

        validation_result = await migration.validate_migration(db=dbs)
        assert not validation_result.errors

    nbr_indexes_after = len(await index_manager.list())
    assert nbr_indexes_after - nbr_indexes_before == 1
