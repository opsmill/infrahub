import pytest

from infrahub.constants.database import IndexType
from infrahub.core.migrations.graph.m085_schema_change_indexes import SCHEMA_CHANGE_INDEXES_TO_ADD, Migration085
from infrahub.core.migrations.shared import MigrationInput
from infrahub.database import DatabaseType, InfrahubDatabase
from infrahub.database.neo4j import IndexManagerNeo4j


async def _existing_indexes(db: InfrahubDatabase) -> set[tuple[str, tuple[str, ...], IndexType]]:
    index_manager = IndexManagerNeo4j(db=db)
    return {(info.label, tuple(info.properties), info.type) for info in await index_manager.list()}


async def test_migration_085(db: InfrahubDatabase) -> None:
    """The schema changes are indexed by uuid and branch, and their applications by uuid."""
    if db.db_type != DatabaseType.NEO4J:
        pytest.skip("The migration only manages Neo4j indexes")

    index_manager = IndexManagerNeo4j(db=db)
    index_manager.init(nodes=SCHEMA_CHANGE_INDEXES_TO_ADD, rels=[])
    await index_manager.drop()

    migration = Migration085()

    before = await migration.validate_migration(db=db)
    assert before.errors == [
        "range index on SchemaChange(uuid) is missing",
        "range index on SchemaChange(branch) is missing",
        "range index on SchemaChangeApplication(uuid) is missing",
    ]

    execution_result = await migration.execute(migration_input=MigrationInput(db=db))
    assert not execution_result.errors

    validation_result = await migration.validate_migration(db=db)
    assert not validation_result.errors

    expected = {
        ("SchemaChange", ("uuid",), IndexType.RANGE),
        ("SchemaChange", ("branch",), IndexType.RANGE),
        ("SchemaChangeApplication", ("uuid",), IndexType.RANGE),
    }
    existing = await _existing_indexes(db=db)
    assert {index for index in existing if index[0].startswith("SchemaChange")} == expected

    second_run = await migration.execute(migration_input=MigrationInput(db=db))
    assert not second_run.errors
    assert await _existing_indexes(db=db) == existing
