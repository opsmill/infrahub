import pytest
from fastapi.testclient import TestClient

from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.message_bus.events import (
    InfrahubRPCResponse,
    MessageType,
    RPCStatusCode,
    TransformMessageAction,
)
from infrahub.message_bus.rpc import InfrahubRpcClientTesting


@pytest.fixture
def client():
    # In order to mock some methods later we can't load app by default because it will automatically load all import in mai.py as well
    from infrahub.main import app

    return TestClient(app)


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
    await q1.new(session=session, name="quer01", query=query)
    await q1.save(session=session)

    r1 = await Node.init(session=session, schema="Repository")
    await r1.new(session=session, name="repo01", location="git@github.com:user/repo01.git")
    await r1.save(session=session)


headers = {"Authorization": "Token XXXX"}


async def test_transform_endpoint(
    session, default_branch, patch_rpc_client, register_core_models_schema, car_person_data
):
    from infrahub.main import app

    client = TestClient(app)

    repositories = await NodeManager.query(session=session, schema="Repository")
    queries = await NodeManager.query(session=session, schema="GraphQLQuery")

    t1 = await Node.init(session=session, schema="TransformPython")
    await t1.new(
        session=session,
        name="transform01",
        query=str(queries[0].id),
        url="mytransform",
        repository=str(repositories[0].id),
        file_path="transform01.py",
        class_name="Transform01",
        rebase=False,
    )
    await t1.save(session=session)

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        mock_response = InfrahubRPCResponse(
            status=RPCStatusCode.OK.value, response={"transformed_data": {"KEY1": "value1", "KEY2": "value2"}}
        )
        await client.app.state.rpc_client.add_response(
            response=mock_response, message_type=MessageType.TRANSFORMATION, action=TransformMessageAction.PYTHON
        )

        response = client.get(
            "/transform/mytransform",
            headers=headers,
        )

    assert response.status_code == 200
    assert response.json() is not None
    result = response.json()

    assert result == {"KEY1": "value1", "KEY2": "value2"}


async def test_transform_endpoint_path(session, patch_rpc_client, default_branch, car_person_data):
    from infrahub.main import app

    client = TestClient(app)

    repositories = await NodeManager.query(session=session, schema="Repository")
    queries = await NodeManager.query(session=session, schema="GraphQLQuery")

    t1 = await Node.init(session=session, schema="TransformPython")
    await t1.new(
        session=session,
        name="transform01",
        query=str(queries[0].id),
        url="my/transform/function",
        repository=str(repositories[0].id),
        file_path="transform01.py",
        class_name="Transform01",
        rebase=False,
    )
    await t1.save(session=session)

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        mock_response = InfrahubRPCResponse(
            status=RPCStatusCode.OK.value, response={"transformed_data": {"KEY1": "value1", "KEY2": "value2"}}
        )
        await client.app.state.rpc_client.add_response(
            response=mock_response, message_type=MessageType.TRANSFORMATION, action=TransformMessageAction.PYTHON
        )

        response = client.get(
            "/transform/my/transform/function",
            headers=headers,
        )

    assert response.status_code == 200
    assert response.json() is not None
    result = response.json()

    assert result == {"KEY1": "value1", "KEY2": "value2"}


async def test_graphql_endpoint(session, client, default_branch, car_person_data):
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

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.post(
            "/graphql",
            json={"query": query},
            headers=headers,
        )

    assert response.status_code == 200
    assert "errors" not in response.json()
    assert response.json()["data"] is not None
    result = response.json()["data"]

    result_per_name = {result["name"]["value"]: result for result in result["person"]}
    assert sorted(result_per_name.keys()) == ["Jane", "John"]
    assert len(result_per_name["John"]["cars"]) == 2
    assert len(result_per_name["Jane"]["cars"]) == 1


async def test_graphql_options(session, client, default_branch, car_person_data):
    await create_branch(branch_name="branch2", session=session)

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.options(
            "/graphql",
            headers=headers,
        )

        assert response.status_code == 200
        assert "Allow" in response.headers
        assert response.headers["Allow"] == "GET, POST, OPTIONS"

        response = client.options(
            "/graphql/branch2",
            headers=headers,
        )

        assert response.status_code == 200
        assert "Allow" in response.headers
        assert response.headers["Allow"] == "GET, POST, OPTIONS"

        response = client.options(
            "/graphql/notvalid",
            headers=headers,
        )

        assert response.status_code == 404
