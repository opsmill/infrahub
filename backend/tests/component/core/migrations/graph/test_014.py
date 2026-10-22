from infrahub.constants.database import IndexType
from infrahub.core.branch.models import Branch
from infrahub.core.migrations.graph.m014_remove_index_attr_value import (
    Migration014,
)
from infrahub.core.migrations.shared import MigrationInput
from infrahub.database import InfrahubDatabase
from infrahub.database.index import IndexItem
from infrahub.database.neo4j import IndexManagerNeo4j


async def test_migration_014(
    db: InfrahubDatabase,
    reset_registry: None,
    default_branch: Branch,
    delete_all_nodes_in_db: None,
) -> None:
    indexes = [
        IndexItem(name="node_uuid", label="Node", properties=["uuid"], type=IndexType.RANGE),
        IndexItem(name="attr_value", label="AttributeValue", properties=["value"], type=IndexType.RANGE),
    ]

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
    assert nbr_indexes_before - nbr_indexes_after == 1
