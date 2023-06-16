from infrahub.core.query.utils import find_node_schema


async def test_find_node_schema(neo4j_factory, group_schema, branch):
    n1 = neo4j_factory.hydrate_node(111, {"Node", "Group", "CoreStandardGroup"}, {"uuid": "n1"}, "111")
    schema = find_node_schema(node=n1, branch=branch)
    assert schema.kind == "CoreStandardGroup"

    n2 = neo4j_factory.hydrate_node(122, {"Node", "CoreGroup"}, {"uuid": "n1"}, "122")
    schema = find_node_schema(node=n2, branch=branch)
    assert schema is None
