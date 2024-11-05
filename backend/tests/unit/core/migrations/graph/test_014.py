from infrahub.core.migrations.graph.m014_remove_index_attr_value import (
    Migration014,
)
from infrahub.database import DatabaseType, InfrahubDatabase
from infrahub.database.constants import IndexType
from infrahub.database.index import IndexItem


async def test_migration_014(
    db: InfrahubDatabase,
    reset_registry,
    default_branch,
    delete_all_nodes_in_db,
):
    indexes = [
        IndexItem(name="node_uuid", label="Node", properties=["uuid"], type=IndexType.RANGE),
        IndexItem(name="attr_value", label="AttributeValue", properties=["value"], type=IndexType.RANGE),
    ]

    db.manager.index.init(nodes=indexes, rels=[])
    await db.manager.index.add()
    nbr_indexes_before = len(await db.manager.index.list())

    async with db.start_session() as dbs:
        migration = Migration014()
        execution_result = await migration.execute(db=dbs)
        assert not execution_result.errors

        validation_result = await migration.validate_migration(db=dbs)
        assert not validation_result.errors

    nbr_indexes_after = len(await db.manager.index.list())
    if db.db_type == DatabaseType.NEO4J:
        assert nbr_indexes_before - nbr_indexes_after == 1
    else:
        assert nbr_indexes_before - nbr_indexes_after == 0
