from infrahub.core.utils import delete_all_nodes, get_paths_between_nodes, element_id_to_id
from infrahub.database import execute_write_query


def test_delete_all_nodes():

    assert delete_all_nodes() == []


def test_element_id_to_id():

    assert element_id_to_id("4:c0814fa2-df5b-4d66-ba5f-9a01817f16fb:167") == 167


def test_get_paths_between_nodes(empty_database):

    query = """
    CREATE (p1:Person { name: "Jim" })
    CREATE (p2:Person { name: "Jane" })
    CREATE (p3:Person { name: "Billy" })
    CREATE (p1)-[r1:KNOWS]->(p2)
    CREATE (p1)-[r2:KNOWS]->(p3)
    CREATE (p1)-[r3:IS_FRIENDS_WITH]->(p2)
    RETURN p1, p2, p3
    """

    results = execute_write_query(query)
    nodes = results[0]

    paths = get_paths_between_nodes(source_id=nodes[0].element_id, destination_id=nodes[1].element_id)
    assert len(paths) == 2

    paths = get_paths_between_nodes(
        source_id=nodes[0].element_id, destination_id=nodes[1].element_id, relationships=["KNOWS"]
    )
    assert len(paths) == 1

    paths = get_paths_between_nodes(source_id=nodes[2].element_id, destination_id=nodes[1].element_id)
    assert len(paths) == 2

    paths = get_paths_between_nodes(
        source_id=nodes[2].element_id, destination_id=nodes[1].element_id, relationships=["KNOWS"]
    )
    assert len(paths) == 1

    paths = get_paths_between_nodes(source_id=nodes[2].element_id, destination_id=nodes[1].element_id, max_length=1)
    assert len(paths) == 0
