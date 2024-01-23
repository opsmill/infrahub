from fastapi.testclient import TestClient

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase


async def test_websocket(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema):
    t2 = await Node.init(db=db, schema=InfrahubKind.TAG, branch=default_branch)
    await t2.new(db=db, name="Red", description="The Red tag")
    await t2.save(db=db)

    q1 = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY, branch=default_branch)
    await q1.new(db=db, name="query01", query="query { BuiltinTag { count }}")
    await q1.save(db=db)

    from infrahub.server import app

    client = TestClient(app)

    with client:
        with client.websocket_connect("/graphql") as websocket:
            websocket.send_json(
                {
                    "id": "1",
                    "type": "start",
                    "payload": {"query": 'subscription {\n  query(name: "query01")\n}', "variables": {}},
                }
            )
            data = websocket.receive_json()
            assert data == {"id": "1", "payload": {"data": {"query": {"BuiltinTag": {"count": 1}}}}, "type": "data"}
