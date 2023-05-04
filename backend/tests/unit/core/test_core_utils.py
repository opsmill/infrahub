from neo4j import AsyncSession

from infrahub.core.utils import (
    count_relationships,
    delete_all_nodes,
    element_id_to_id,
    get_paths_between_nodes,
)
from infrahub.database import execute_write_query_async


async def test_delete_all_nodes(session: AsyncSession):
    assert await delete_all_nodes(session) == []


def test_element_id_to_id():
    assert element_id_to_id("4:c0814fa2-df5b-4d66-ba5f-9a01817f16fb:167") == 167


async def test_get_paths_between_nodes(session: AsyncSession, empty_database):
    query = """
    CREATE (p1:Person { name: "Jim" })
    CREATE (p2:Person { name: "Jane" })
    CREATE (p3:Person { name: "Billy" })
    CREATE (p1)-[r1:KNOWS]->(p2)
    CREATE (p1)-[r2:KNOWS]->(p3)
    CREATE (p1)-[r3:IS_FRIENDS_WITH]->(p2)
    RETURN p1, p2, p3
    """

    results = await execute_write_query_async(session=session, query=query)
    nodes = results[0]

    paths = await get_paths_between_nodes(
        session=session, source_id=nodes[0].element_id, destination_id=nodes[1].element_id
    )
    assert len(paths) == 2

    paths = await get_paths_between_nodes(
        session=session, source_id=nodes[0].element_id, destination_id=nodes[1].element_id, relationships=["KNOWS"]
    )
    assert len(paths) == 1

    paths = await get_paths_between_nodes(
        session=session, source_id=nodes[2].element_id, destination_id=nodes[1].element_id
    )
    assert len(paths) == 2

    paths = await get_paths_between_nodes(
        session=session, source_id=nodes[2].element_id, destination_id=nodes[1].element_id, relationships=["KNOWS"]
    )
    assert len(paths) == 1

    paths = await get_paths_between_nodes(
        session=session, source_id=nodes[2].element_id, destination_id=nodes[1].element_id, max_length=1
    )
    assert len(paths) == 0


async def test_count_relationships(session: AsyncSession, empty_database):
    query = """
    CREATE (p1:Person { name: "Jim" })
    CREATE (p2:Person { name: "Jane" })
    CREATE (p3:Person { name: "Billy" })
    CREATE (p1)-[r1:KNOWS]->(p2)
    CREATE (p1)-[r2:KNOWS]->(p3)
    CREATE (p1)-[r3:IS_FRIENDS_WITH]->(p2)
    RETURN p1, p2, p3
    """

    await execute_write_query_async(session=session, query=query)

    assert await count_relationships(session=session) == 3
