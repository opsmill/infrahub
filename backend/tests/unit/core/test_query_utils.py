from infrahub.core.constants import InfrahubKind
from infrahub.core.query.utils import find_node_schema


async def test_find_node_schema(db, neo4j_factory, group_schema, branch):
    n1 = neo4j_factory.hydrate_node(111, {"Node", "Group", InfrahubKind.STANDARDGROUP}, {"uuid": "n1"}, "111")
    schema = find_node_schema(db=db, node=n1, branch=branch, duplicate=True)
    assert schema.kind == InfrahubKind.STANDARDGROUP

    n2 = neo4j_factory.hydrate_node(122, {"Node", InfrahubKind.GENERICGROUP}, {"uuid": "n1"}, "122")
    schema = find_node_schema(db=db, node=n2, branch=branch)
    assert schema is None
