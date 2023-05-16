import pytest
from fastapi.testclient import TestClient

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
def patch_rpc_client():
    import infrahub.message_bus.rpc

    infrahub.message_bus.rpc.InfrahubRpcClient = InfrahubRpcClientTesting


async def test_transform_endpoint(
    session, client_headers, default_branch, patch_rpc_client, register_core_models_schema, car_person_data
):
    from infrahub.api.main import app

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
            status=RPCStatusCode.OK, response={"transformed_data": {"KEY1": "value1", "KEY2": "value2"}}
        )
        await client.app.state.rpc_client.add_response(
            response=mock_response, message_type=MessageType.TRANSFORMATION, action=TransformMessageAction.PYTHON
        )

        response = client.get(
            "/transform/mytransform",
            headers=client_headers,
        )

    assert response.status_code == 200
    assert response.json() is not None
    result = response.json()

    assert result == {"KEY1": "value1", "KEY2": "value2"}


async def test_transform_endpoint_path(session, client_headers, patch_rpc_client, default_branch, car_person_data):
    from infrahub.api.main import app

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
            status=RPCStatusCode.OK, response={"transformed_data": {"KEY1": "value1", "KEY2": "value2"}}
        )
        await client.app.state.rpc_client.add_response(
            response=mock_response, message_type=MessageType.TRANSFORMATION, action=TransformMessageAction.PYTHON
        )

        response = client.get(
            "/transform/my/transform/function",
            headers=client_headers,
        )

    assert response.status_code == 200
    assert response.json() is not None
    result = response.json()

    assert result == {"KEY1": "value1", "KEY2": "value2"}
