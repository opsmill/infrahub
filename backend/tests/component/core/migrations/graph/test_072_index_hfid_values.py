from infrahub.core.attribute import MAX_STRING_LENGTH
from infrahub.core.branch import Branch
from infrahub.core.migrations.graph.m072_index_hfid_values import Migration072
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.timestamp import current_timestamp
from infrahub.database import InfrahubDatabase


async def test_migration_072_normalizes_and_indexes(db: InfrahubDatabase, default_branch: Branch) -> None:
    """HFID values with non-string elements should be normalized to all-strings and indexed."""
    at = current_timestamp()

    create_test_data_query = """
    CREATE (n1:Node {uuid: "node-1"})
    CREATE (attr1:Attribute {name: "human_friendly_id", uuid: "attr-1"})
    CREATE (av1:AttributeValue {value: '["*","*","view",4]', is_default: false})
    CREATE (n1)-[:HAS_ATTRIBUTE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(attr1)
    CREATE (attr1)-[:HAS_VALUE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(av1)

    CREATE (n2:Node {uuid: "node-2"})
    CREATE (attr2:Attribute {name: "human_friendly_id", uuid: "attr-2"})
    CREATE (av2:AttributeValue:AttributeValueIndexed {value: '["ns2","name2"]', is_default: false})
    CREATE (n2)-[:HAS_ATTRIBUTE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(attr2)
    CREATE (attr2)-[:HAS_VALUE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(av2)
    """
    await db.execute_query(query=create_test_data_query, params={"branch": default_branch.name, "at": at})

    migration = Migration072()
    result = await migration.execute(MigrationInput(db=db))
    assert not result.errors

    check_query = """
    MATCH (attr:Attribute {name: "human_friendly_id"})-[:HAS_VALUE]->(av)
    RETURN attr.uuid AS attr_uuid, av.value AS value, av:AttributeValueIndexed AS is_indexed
    ORDER BY attr.uuid
    """
    results = await db.execute_query(query=check_query)
    assert len(results) == 2

    assert results[0].get("attr_uuid") == "attr-1"
    assert results[0].get("value") == '["*","*","view","4"]'
    assert results[0].get("is_indexed") is True

    assert results[1].get("attr_uuid") == "attr-2"
    assert results[1].get("value") == '["ns2","name2"]'
    assert results[1].get("is_indexed") is True

    # Run migration a second time to verify idempotency
    result2 = await migration.execute(MigrationInput(db=db))
    assert not result2.errors

    results2 = await db.execute_query(query=check_query)
    assert len(results2) == 2
    assert results2[0].get("value") == '["*","*","view","4"]'
    assert results2[0].get("is_indexed") is True
    assert results2[1].get("value") == '["ns2","name2"]'
    assert results2[1].get("is_indexed") is True


async def test_migration_072_skips_oversized_values(db: InfrahubDatabase, default_branch: Branch) -> None:
    """HFID values exceeding MAX_STRING_LENGTH should NOT get the indexed label."""
    at = current_timestamp()
    oversized_value = '["' + "x" * MAX_STRING_LENGTH + '"]'

    create_test_data_query = """
    CREATE (n:Node {uuid: "node-oversized"})
    CREATE (attr:Attribute {name: "human_friendly_id", uuid: "attr-oversized"})
    CREATE (av:AttributeValue {value: $oversized_value, is_default: false})
    CREATE (n)-[:HAS_ATTRIBUTE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(attr)
    CREATE (attr)-[:HAS_VALUE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(av)
    """
    await db.execute_query(
        query=create_test_data_query,
        params={"branch": default_branch.name, "at": at, "oversized_value": oversized_value},
    )

    migration = Migration072()
    await migration.execute(MigrationInput(db=db))

    check_query = """
    MATCH (attr:Attribute {uuid: "attr-oversized"})-[:HAS_VALUE]->(av)
    RETURN av:AttributeValueIndexed AS is_indexed
    """
    results = await db.execute_query(query=check_query)
    assert len(results) == 1
    assert results[0].get("is_indexed") is False
