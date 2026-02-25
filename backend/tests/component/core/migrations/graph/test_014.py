from infrahub.constants.database import IndexType
from infrahub.core.migrations.graph.m014_remove_index_attr_value import (
    Migration014,
)
from infrahub.core.migrations.shared import MigrationInput
from infrahub.database import DatabaseType, InfrahubDatabase
from infrahub.database.index import IndexItem
from infrahub.database.memgraph import IndexManagerMemgraph
from infrahub.database.neo4j import IndexManagerNeo4j


async def test_migration_014(
    db: InfrahubDatabase,
    reset_registry,
    default_branch,
    delete_all_nodes_in_db,
) -> None:
    indexes = [
        IndexItem(name="node_uuid", label="Node", properties=["uuid"], type=IndexType.RANGE),
        IndexItem(name="attr_value", label="AttributeValue", properties=["value"], type=IndexType.RANGE),
    ]

    if db.db_type is DatabaseType.MEMGRAPH:
        index_manager = IndexManagerMemgraph(db=db)
    index_manager = IndexManagerNeo4j(db=db)
    index_manager.init(nodes=indexes, rels=[])
    await index_manager.add()
    nbr_indexes_before = len(await index_manager.list())

    async with db.start_session() as dbs:
        migration = Migration014()
        execution_result = await migration.execute(migration_input=MigrationInput(db=dbs))
        assert not execution_result.errors

        validation_result = await migration.validate_migration(db=dbs)
        assert not validation_result.errors

    nbr_indexes_after = len(await index_manager.list())
    if db.db_type == DatabaseType.NEO4J:
        assert nbr_indexes_before - nbr_indexes_after == 1
    else:
        assert nbr_indexes_before - nbr_indexes_after == 0
