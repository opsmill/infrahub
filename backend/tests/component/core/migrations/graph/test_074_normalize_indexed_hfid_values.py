from infrahub.core.branch import Branch
from infrahub.core.migrations.graph.m074_normalize_indexed_hfid_values import Migration074
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.timestamp import current_timestamp
from infrahub.database import InfrahubDatabase


async def test_migration_074_normalizes_indexed_int_value(db: InfrahubDatabase, default_branch: Branch) -> None:
    """An already-indexed integer HFID value is normalized to strings, stays indexed, the old node is removed, and a second run is a no-op."""
    at = current_timestamp()
    create_query = """
    CREATE (n:Node {uuid: "m74a-node"})
    CREATE (attr:Attribute {name: "human_friendly_id", uuid: "m74a-attr"})
    CREATE (av:AttributeValue:AttributeValueIndexed {value: '[650001]', is_default: false})
    CREATE (n)-[:HAS_ATTRIBUTE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(attr)
    CREATE (attr)-[:HAS_VALUE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(av)
    """
    await db.execute_query(query=create_query, params={"branch": default_branch.name, "at": at})

    # The integer-typed value node exists before the migration runs.
    before = await db.execute_query(query="MATCH (av:AttributeValue {value: '[650001]'}) RETURN count(av) AS c")
    assert before[0].get("c") == 1

    migration = Migration074()
    check_query = """
    MATCH (attr:Attribute {uuid: "m74a-attr"})-[:HAS_VALUE]->(av)
    RETURN av.value AS value, av:AttributeValueIndexed AS is_indexed
    """

    for _ in range(2):  # second run must be a no-op
        assert not (await migration.execute(MigrationInput(db=db))).errors
        results = await db.execute_query(query=check_query)
        assert len(results) == 1
        assert results[0].get("value") == '["650001"]'
        assert results[0].get("is_indexed") is True

    # The old integer-typed node is removed once it no longer carries any edge.
    orphan = await db.execute_query(query="MATCH (av:AttributeValue {value: '[650001]'}) RETURN count(av) AS c")
    assert orphan[0].get("c") == 0


async def test_migration_074_repairs_value_shared_across_attrs(db: InfrahubDatabase, default_branch: Branch) -> None:
    """A value shared by two HFID attrs and a non-HFID attr: the HFID edges dedupe onto one node; the original survives for the non-HFID attr."""
    at = current_timestamp()
    create_query = """
    CREATE (shared:AttributeValue:AttributeValueIndexed {value: '[650004]', is_default: false})
    CREATE (n1:Node {uuid: "m74b-node1"})
    CREATE (h1:Attribute {name: "human_friendly_id", uuid: "m74b-h1"})
    CREATE (n1)-[:HAS_ATTRIBUTE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(h1)
    CREATE (h1)-[:HAS_VALUE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(shared)
    CREATE (n2:Node {uuid: "m74b-node2"})
    CREATE (h2:Attribute {name: "human_friendly_id", uuid: "m74b-h2"})
    CREATE (n2)-[:HAS_ATTRIBUTE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(h2)
    CREATE (h2)-[:HAS_VALUE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(shared)
    CREATE (n3:Node {uuid: "m74b-node3"})
    CREATE (other:Attribute {name: "asn", uuid: "m74b-other"})
    CREATE (n3)-[:HAS_ATTRIBUTE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(other)
    CREATE (other)-[:HAS_VALUE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(shared)
    """
    await db.execute_query(query=create_query, params={"branch": default_branch.name, "at": at})

    result = await Migration074().execute(MigrationInput(db=db))
    assert not result.errors

    hfid_query = """
    MATCH (attr:Attribute)-[:HAS_VALUE]->(av)
    WHERE attr.uuid IN ["m74b-h1", "m74b-h2"]
    RETURN attr.uuid AS attr_uuid, av.value AS value, elementId(av) AS av_id, av:AttributeValueIndexed AS is_indexed
    """
    by_attr = {record.get("attr_uuid"): record for record in await db.execute_query(query=hfid_query)}
    assert by_attr["m74b-h1"].get("value") == '["650004"]'
    assert by_attr["m74b-h2"].get("value") == '["650004"]'
    assert by_attr["m74b-h1"].get("is_indexed") is True
    assert by_attr["m74b-h2"].get("is_indexed") is True
    # Both HFID attributes resolve to the same deduplicated node.
    assert by_attr["m74b-h1"].get("av_id") == by_attr["m74b-h2"].get("av_id")

    # The original node survives because the non-HFID attribute still references it.
    other = await db.execute_query(
        query="MATCH (a:Attribute {uuid: 'm74b-other'})-[:HAS_VALUE]->(av) RETURN av.value AS value"
    )
    assert len(other) == 1
    assert other[0].get("value") == "[650004]"


async def test_migration_074_normalizes_indexed_values_across_pages(
    db: InfrahubDatabase, default_branch: Branch
) -> None:
    """Every indexed integer HFID value is normalized even when they span multiple pagination batches."""
    at = current_timestamp()
    node_count = 12
    create_query = """
    UNWIND range(1, $node_count) AS i
    CREATE (n:Node {uuid: "m74d-node-" + toString(i)})
    CREATE (attr:Attribute {name: "human_friendly_id", uuid: "m74d-attr-" + toString(i)})
    CREATE (av:AttributeValue:AttributeValueIndexed {value: "[7770" + toString(i) + "]", is_default: false})
    CREATE (n)-[:HAS_ATTRIBUTE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(attr)
    CREATE (attr)-[:HAS_VALUE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(av)
    """
    await db.execute_query(
        query=create_query, params={"branch": default_branch.name, "at": at, "node_count": node_count}
    )

    migration = Migration074()
    migration.update_batch_size = 2  # force multiple pagination batches
    result = await migration.execute(MigrationInput(db=db))
    assert not result.errors

    check_query = """
    MATCH (attr:Attribute {name: "human_friendly_id"})-[:HAS_VALUE]->(av)
    WHERE attr.uuid STARTS WITH "m74d-attr-"
    RETURN av.value AS value, av:AttributeValueIndexed AS is_indexed
    """
    results = await db.execute_query(query=check_query)
    values = [record.get("value") for record in results]

    assert len(values) == node_count
    unnormalized = sorted(value for value in values if '"' not in value)
    assert unnormalized == []
    assert all(record.get("is_indexed") for record in results)


async def test_migration_074_normalizes_plain_int_value(db: InfrahubDatabase, default_branch: Branch) -> None:
    """A non-indexed integer HFID value is normalized to strings and stays non-indexed."""
    at = current_timestamp()
    create_query = """
    CREATE (n:Node {uuid: "m74f-node"})
    CREATE (attr:Attribute {name: "human_friendly_id", uuid: "m74f-attr"})
    CREATE (av:AttributeValue {value: '[650005]', is_default: false})
    CREATE (n)-[:HAS_ATTRIBUTE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(attr)
    CREATE (attr)-[:HAS_VALUE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(av)
    """
    await db.execute_query(query=create_query, params={"branch": default_branch.name, "at": at})

    result = await Migration074().execute(MigrationInput(db=db))
    assert not result.errors

    check_query = """
    MATCH (attr:Attribute {uuid: "m74f-attr"})-[:HAS_VALUE]->(av)
    RETURN av.value AS value, av:AttributeValueIndexed AS is_indexed
    """
    results = await db.execute_query(query=check_query)
    assert len(results) == 1
    assert results[0].get("value") == '["650005"]'
    assert results[0].get("is_indexed") is False


async def test_migration_074_normalizes_non_integer_types(db: InfrahubDatabase, default_branch: Branch) -> None:
    """Non-integer elements (float, negative number) are also converted, and the value stays indexed."""
    at = current_timestamp()
    create_query = """
    CREATE (n:Node {uuid: "m74g-node"})
    CREATE (attr:Attribute {name: "human_friendly_id", uuid: "m74g-attr"})
    CREATE (av:AttributeValue:AttributeValueIndexed {value: '[3.14, -8, 99]', is_default: false})
    CREATE (n)-[:HAS_ATTRIBUTE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(attr)
    CREATE (attr)-[:HAS_VALUE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(av)
    """
    await db.execute_query(query=create_query, params={"branch": default_branch.name, "at": at})

    result = await Migration074().execute(MigrationInput(db=db))
    assert not result.errors

    check_query = """
    MATCH (attr:Attribute {uuid: "m74g-attr"})-[:HAS_VALUE]->(av)
    RETURN av.value AS value, av:AttributeValueIndexed AS is_indexed
    """
    results = await db.execute_query(query=check_query)
    assert len(results) == 1
    assert results[0].get("value") == '["3.14","-8","99"]'
    assert results[0].get("is_indexed") is True


async def test_migration_074_does_not_relabel_shared_plain_node(db: InfrahubDatabase, default_branch: Branch) -> None:
    """A normalized value that already exists as a plain node elsewhere gets its own indexed node; the plain one is untouched."""
    at = current_timestamp()
    create_query = """
    CREATE (plain:AttributeValue {value: '["650006"]', is_default: false})
    CREATE (dn:Node {uuid: "m74h-desc-node"})
    CREATE (desc:Attribute {name: "description", uuid: "m74h-desc"})
    CREATE (dn)-[:HAS_ATTRIBUTE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(desc)
    CREATE (desc)-[:HAS_VALUE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(plain)
    CREATE (hn:Node {uuid: "m74h-hfid-node"})
    CREATE (hfid:Attribute {name: "human_friendly_id", uuid: "m74h-hfid"})
    CREATE (iav:AttributeValue:AttributeValueIndexed {value: '[650006]', is_default: false})
    CREATE (hn)-[:HAS_ATTRIBUTE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(hfid)
    CREATE (hfid)-[:HAS_VALUE {branch: $branch, branch_level: 1, status: "active", from: $at}]->(iav)
    """
    await db.execute_query(query=create_query, params={"branch": default_branch.name, "at": at})

    result = await Migration074().execute(MigrationInput(db=db))
    assert not result.errors

    # The non-HFID attribute keeps its plain, non-indexed node.
    desc = await db.execute_query(
        query="""
        MATCH (a:Attribute {uuid: "m74h-desc"})-[:HAS_VALUE]->(av)
        RETURN av.value AS value, av:AttributeValueIndexed AS is_indexed, elementId(av) AS av_id
        """
    )
    assert len(desc) == 1
    assert desc[0].get("value") == '["650006"]'
    assert desc[0].get("is_indexed") is False

    # The HFID attribute gets its own indexed node with the normalized value.
    hfid = await db.execute_query(
        query="""
        MATCH (a:Attribute {uuid: "m74h-hfid"})-[:HAS_VALUE]->(av)
        RETURN av.value AS value, av:AttributeValueIndexed AS is_indexed, elementId(av) AS av_id
        """
    )
    assert len(hfid) == 1
    assert hfid[0].get("value") == '["650006"]'
    assert hfid[0].get("is_indexed") is True

    # They are distinct nodes; the plain node was not relabeled.
    assert desc[0].get("av_id") != hfid[0].get("av_id")
