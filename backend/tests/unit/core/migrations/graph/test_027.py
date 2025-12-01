from infrahub.core.migrations.graph.m027_delete_isolated_nodes import Migration027
from infrahub.database import InfrahubDatabase


async def test_migration_027(
    db: InfrahubDatabase,
    default_branch,
) -> None:
    query = """
    CREATE (valid_node:Node {uuid: '123'})
    CREATE (isolated_node:Node {uuid: '456'})
    CREATE (root:Root {name: 'RootNode'})

    CREATE (isolated_node)-[r1:IS_RELATED {branch: '-global-'}]->(valid_node)
    CREATE (valid_node)-[r3:IS_PART_OF]->(root)

    RETURN valid_node, isolated_node
    """

    results = await db.execute_query(query=query)
    assert len(results) == 1

    migration = Migration027()
    execution_result = await migration.execute(db=db)
    assert not execution_result.errors

    validation_result = await migration.validate_migration(db=db)
    assert not validation_result.errors

    query = """
    MATCH (n: Node)
    WHERE n.uuid = '456'
    RETURN n
    """

    results = await db.execute_query(query=query)
    assert len(results) == 0
