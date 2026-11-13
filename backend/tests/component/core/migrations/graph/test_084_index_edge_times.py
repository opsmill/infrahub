import pytest

from infrahub.constants.database import IndexType
from infrahub.core.migrations.graph.m084_index_edge_times import EDGE_TIME_INDEXES_TO_ADD, Migration084
from infrahub.core.migrations.shared import MigrationInput
from infrahub.database import DatabaseType, InfrahubDatabase
from infrahub.database.neo4j import IndexManagerNeo4j


async def _existing_indexes(db: InfrahubDatabase) -> set[tuple[str, tuple[str, ...], IndexType]]:
    index_manager = IndexManagerNeo4j(db=db)
    return {(info.label, tuple(info.properties), info.type) for info in await index_manager.list()}


async def test_migration_084(db: InfrahubDatabase) -> None:
    """Every edge type gains a RANGE index on `from` and on `to`, apart from the two `from` indexes that exist."""
    if db.db_type != DatabaseType.NEO4J:
        pytest.skip("The migration only manages Neo4j indexes")

    # Reproduce the pre-migration state: none of the indexes the migration adds exists.
    index_manager = IndexManagerNeo4j(db=db)
    index_manager.init(nodes=[], rels=EDGE_TIME_INDEXES_TO_ADD)
    await index_manager.drop()

    migration = Migration084()

    # A clean validation after the run only means something if it was dirty before.
    before = await migration.validate_migration(db=db)
    assert before.errors == [
        "range index on HAS_ATTRIBUTE(to) is missing",
        "range index on HAS_OWNER(from) is missing",
        "range index on HAS_OWNER(to) is missing",
        "range index on HAS_SOURCE(from) is missing",
        "range index on HAS_SOURCE(to) is missing",
        "range index on HAS_VALUE(to) is missing",
        "range index on IS_PART_OF(from) is missing",
        "range index on IS_PART_OF(to) is missing",
        "range index on IS_PROTECTED(from) is missing",
        "range index on IS_PROTECTED(to) is missing",
        "range index on IS_RELATED(from) is missing",
        "range index on IS_RELATED(to) is missing",
        "range index on IS_RESERVED(from) is missing",
        "range index on IS_RESERVED(to) is missing",
    ]

    execution_result = await migration.execute(migration_input=MigrationInput(db=db))
    assert not execution_result.errors

    validation_result = await migration.validate_migration(db=db)
    assert not validation_result.errors

    existing = await _existing_indexes(db=db)
    assert {
        (edge_type, (edge_property,), IndexType.RANGE)
        for edge_type in (
            "HAS_ATTRIBUTE",
            "HAS_OWNER",
            "HAS_SOURCE",
            "HAS_VALUE",
            "IS_PART_OF",
            "IS_PROTECTED",
            "IS_RELATED",
            "IS_RESERVED",
        )
        for edge_property in ("from", "to")
    } <= existing

    states = await db.execute_query(
        query="SHOW INDEXES YIELD labelsOrTypes, properties, state WHERE properties IN [['from'], ['to']] RETURN state",
        params={},
        name="test_index_states",
    )
    assert {row["state"] for row in states} == {"ONLINE"}

    # Running it again is a no-op.
    second_run = await migration.execute(migration_input=MigrationInput(db=db))
    assert not second_run.errors
