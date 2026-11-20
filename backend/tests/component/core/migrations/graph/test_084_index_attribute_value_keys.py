import hashlib
from typing import Any

import pytest

from infrahub.core.branch import Branch
from infrahub.core.graph.schema import get_attribute_value_key
from infrahub.core.migrations.graph.m084_index_attribute_value_keys import (
    UPDATE_BATCH_SIZE,
    VALUE_KEY_INDEX,
    AttributeValuesPendingKeyQuery,
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


async def _pending_value_count(db: InfrahubDatabase) -> int:
    results = await db.execute_query(query="MATCH (av:AttributeValueKeyPending) RETURN count(av) AS count")
    return results[0]["count"]


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


async def test_migration_084_keys_values_across_batches(db: InfrahubDatabase, default_branch: Branch) -> None:
    """Every value without a key gets the hash of its value when the values span several batches."""
    if db.db_type != DatabaseType.NEO4J:
        pytest.skip("The migration only manages Neo4j indexes")

    # One value more than a batch, so a full batch is followed by a partial one.
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
    assert await _pending_value_count(db=db) == 0


async def test_migration_084_keys_values_left_labelled_by_an_interrupted_run(
    db: InfrahubDatabase, default_branch: Branch
) -> None:
    """Values an interrupted run labelled and values it never reached both get their key, and the label goes."""
    if db.db_type != DatabaseType.NEO4J:
        pytest.skip("The migration only manages Neo4j indexes")

    values = ["labelled-1", "labelled-2", "unlabelled-1", "unlabelled-2"]
    await db.execute_query(
        query="UNWIND $values AS value CREATE (:AttributeValue {value: value, is_default: false})",
        params={"values": values},
    )
    await db.execute_query(
        query="MATCH (av:AttributeValue) WHERE av.value STARTS WITH 'labelled-' SET av:AttributeValueKeyPending"
    )
    assert await _pending_value_count(db=db) == 2

    migration = Migration084()
    result = await migration.execute(migration_input=MigrationInput(db=db))
    assert not result.errors

    rows = await db.execute_query(
        query="""
        MATCH (av:AttributeValue)
        WHERE av.value IN $values
        RETURN av.value AS value, av.value_key AS value_key, labels(av) AS labels
        """,
        params={"values": values},
    )
    assert {row["value"]: (row["value_key"], row["labels"]) for row in rows} == {
        "labelled-1": ("c978a9d1708c77695a1f0200154eb8f8", ["AttributeValue"]),
        "labelled-2": ("ed094783f743ac484ebb9e2399e7b3a5", ["AttributeValue"]),
        "unlabelled-1": ("3d73a897349f46415922e4fbcb478c6e", ["AttributeValue"]),
        "unlabelled-2": ("ec5192df43b8affad08a77613d88b3cf", ["AttributeValue"]),
    }
    validation_result = await migration.validate_migration(db=db)
    assert not validation_result.errors


def _vertex_reads(plan: dict[str, Any]) -> list[str]:
    operator = plan["operatorType"].removesuffix("@neo4j")
    reads = [f"{operator} {plan['args']['Details']}"] if operator.endswith(("Scan", "Seek")) else []
    return reads + [read for child in plan.get("children", []) for read in _vertex_reads(child)]


async def test_migration_084_batch_read_scans_only_the_labelled_values(
    db: InfrahubDatabase, default_branch: Branch
) -> None:
    """A batch finds its values through the label of the values waiting for a key, not through every value."""
    if db.db_type != DatabaseType.NEO4J:
        pytest.skip("The migration only manages Neo4j indexes")

    query = await AttributeValuesPendingKeyQuery.init(db=db, limit=UPDATE_BATCH_SIZE)
    rendered = query.render()
    _, metadata = await db.execute_query_with_metadata(
        query="EXPLAIN\n" + rendered.text, params=rendered.params, name="explain_pending_values"
    )

    assert _vertex_reads(metadata["plan"]) == ["NodeByLabelScan av:AttributeValueKeyPending"]
