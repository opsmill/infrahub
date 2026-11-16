import hashlib
from collections.abc import Generator

import pytest

from infrahub import config
from infrahub.core.branch import Branch
from infrahub.core.graph.schema import get_attribute_value_key
from infrahub.core.migrations.graph.m084_index_attribute_value_keys import (
    UPDATE_BATCH_SIZE,
    VALUE_KEY_INDEX,
    Migration084,
)
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.schema import NodeSchema
from infrahub.database import DatabaseType, InfrahubDatabase
from infrahub.database.neo4j import IndexManagerNeo4j

NODE_VALUE_KEYS_QUERY = """
MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(attr:Attribute)-[:HAS_VALUE]->(av:AttributeValue)
WHERE attr.name IN ["mytextarea", "myjson"]
RETURN attr.name AS name, av.value_key AS value_key
"""


async def _node_value_keys(db: InfrahubDatabase, node_id: str) -> dict[str, str | None]:
    results = await db.execute_query(query=NODE_VALUE_KEYS_QUERY, params={"node_id": node_id})
    return {result["name"]: result["value_key"] for result in results}


async def test_migration_084(
    db: InfrahubDatabase, default_branch: Branch, all_attribute_types_schema: NodeSchema
) -> None:
    """Values of large kinds without a key get the hash of their value, and the key index appears."""
    if db.db_type != DatabaseType.NEO4J:
        pytest.skip("The migration only manages Neo4j indexes")

    node = await Node.init(db=db, schema=all_attribute_types_schema)
    await node.new(db=db, mytextarea="text value", myjson={"value": {"id": "value"}})
    await node.save(db=db)

    # Reproduce the pre-migration state: no value carries a key and the index does not exist.
    await db.execute_query(query="MATCH (av:AttributeValue) WHERE av.value_key IS NOT NULL REMOVE av.value_key")
    index_manager = IndexManagerNeo4j(db=db)
    index_manager.init(nodes=[VALUE_KEY_INDEX], rels=[])
    await index_manager.drop()

    migration = Migration084()

    # A clean validation after the run only means something if it was dirty before.
    before = await migration.validate_migration(db=db)
    assert before.errors[-1] == "range index on AttributeValue(value_key) is missing"
    assert before.errors[0].endswith("non-indexed attribute values have no key")
    assert await _node_value_keys(db=db, node_id=node.id) == {"mytextarea": None, "myjson": None}

    execution_result = await migration.execute(migration_input=MigrationInput(db=db))
    assert not execution_result.errors

    validation_result = await migration.validate_migration(db=db)
    assert not validation_result.errors
    expected = {
        "mytextarea": get_attribute_value_key("text value"),
        "myjson": get_attribute_value_key('{"id":"value"}'),
    }
    assert await _node_value_keys(db=db, node_id=node.id) == expected

    # Running it again is a no-op.
    second_run = await migration.execute(migration_input=MigrationInput(db=db))
    assert not second_run.errors
    assert await _node_value_keys(db=db, node_id=node.id) == expected


READ_PAGE_SIZE = 300


@pytest.fixture
def small_read_pages() -> Generator[None, None, None]:
    original = config.SETTINGS.database.query_size_limit
    config.SETTINGS.database.query_size_limit = READ_PAGE_SIZE
    yield
    config.SETTINGS.database.query_size_limit = original


async def test_migration_084_keys_values_across_read_pages_and_write_batches(
    db: InfrahubDatabase, default_branch: Branch, small_read_pages: None
) -> None:
    """Every value without a key gets the hash of its value when the values span several pages and batches."""
    if db.db_type != DatabaseType.NEO4J:
        pytest.skip("The migration only manages Neo4j indexes")

    # Neither the read page size nor the write batch size divides this count, so both end with a partial chunk.
    count = UPDATE_BATCH_SIZE + 1
    await db.execute_query(
        query="UNWIND range(1, $count) AS i CREATE (:AttributeValue {value: 'value-' + toString(i), is_default: false})",
        params={"count": count},
    )

    result = await Migration084().execute(migration_input=MigrationInput(db=db))
    assert not result.errors

    rows = await db.execute_query(
        query="""
        MATCH (av:AttributeValue)
        WHERE av.value STARTS WITH 'value-'
        RETURN av.value AS value, av.value_key AS value_key
        """
    )
    assert len(rows) == count
    assert {row["value"]: row["value_key"] for row in rows} == {
        f"value-{index}": hashlib.md5(f"value-{index}".encode(), usedforsecurity=False).hexdigest()
        for index in range(1, count + 1)
    }
