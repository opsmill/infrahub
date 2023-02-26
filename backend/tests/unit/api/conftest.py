import pytest
from fastapi.testclient import TestClient

from infrahub.core.node import Node
from infrahub.message_bus.rpc import InfrahubRpcClientTesting


@pytest.fixture
def client():
    # In order to mock some methods later we can't load app by default because it will automatically load all import in main.py as well
    from infrahub.main import app

    return TestClient(app)


@pytest.fixture
def client_headers():
    return {"Authorization": "Token XXXX"}


@pytest.fixture
def patch_rpc_client():
    import infrahub.message_bus.rpc

    infrahub.message_bus.rpc.InfrahubRpcClient = InfrahubRpcClientTesting


@pytest.fixture
async def car_person_data(session, car_person_schema, register_core_models_schema):
    p1 = await Node.init(session=session, schema="Person")
    await p1.new(session=session, name="John", height=180)
    await p1.save(session=session)
    p2 = await Node.init(session=session, schema="Person")
    await p2.new(session=session, name="Jane", height=170)
    await p2.save(session=session)
    c1 = await Node.init(session=session, schema="Car")
    await c1.new(session=session, name="volt", nbr_seats=4, is_electric=True, owner=p1)
    await c1.save(session=session)
    c2 = await Node.init(session=session, schema="Car")
    await c2.new(session=session, name="bolt", nbr_seats=4, is_electric=True, owner=p1)
    await c2.save(session=session)
    c3 = await Node.init(session=session, schema="Car")
    await c3.new(session=session, name="nolt", nbr_seats=4, is_electric=True, owner=p2)
    await c3.save(session=session)

    query = """
    query {
        person {
            name {
                value
            }
            cars {
                name {
                    value
                }
            }
        }
    }
    """

    q1 = await Node.init(session=session, schema="GraphQLQuery")
    await q1.new(session=session, name="query01", query=query)
    await q1.save(session=session)

    r1 = await Node.init(session=session, schema="Repository")
    await r1.new(session=session, name="repo01", location="git@github.com:user/repo01.git")
    await r1.save(session=session)
