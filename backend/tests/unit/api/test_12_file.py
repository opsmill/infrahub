import pytest
from fastapi.testclient import TestClient

from infrahub.core.node import Node
from infrahub.message_bus.events import (
    GitMessageAction,
    InfrahubRPCResponse,
    MessageType,
    RPCStatusCode,
)
from infrahub.message_bus.rpc import InfrahubRpcClientTesting


@pytest.fixture
def patch_rpc_client():
    import infrahub.message_bus.rpc

    infrahub.message_bus.rpc.InfrahubRpcClient = InfrahubRpcClientTesting


async def test_get_file(
    session,
    client_headers,
    default_branch,
    patch_rpc_client,
    register_core_models_schema,
):
    from infrahub.server import app

    client = TestClient(app)

    r1 = await Node.init(session=session, schema="CoreRepository")
    await r1.new(session=session, name="repo01", location="git@github.com:user/repo01.git")
    await r1.save(session=session)

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        mock_response = InfrahubRPCResponse(status=RPCStatusCode.OK, response={"content": "file content"})

        # No commit yet
        response = client.get(
            f"/api/file/{r1.id}/myfile.text",
            headers=client_headers,
        )
        assert response.status_code == 400

        # With Manual Commit
        await client.app.state.rpc_client.add_response(
            response=mock_response, message_type=MessageType.GIT, action=GitMessageAction.GET_FILE
        )

        response = client.get(
            f"/api/file/{r1.id}/myfile.text?commit=12345678iuytrewqwertyu",
            headers=client_headers,
        )

        assert response.status_code == 200
        assert response.text == "file content"

        # With Commit associated with Repository Object
        r1.commit.value = "1345754212345678iuytrewqwertyu"
        await r1.save(session=session)

        await client.app.state.rpc_client.add_response(
            response=mock_response, message_type=MessageType.GIT, action=GitMessageAction.GET_FILE
        )

        response = client.get(
            f"/api/file/{r1.id}/myfile.text",
            headers=client_headers,
        )

        assert response.status_code == 200
        assert response.text == "file content"

        # Access Repo by name
        await client.app.state.rpc_client.add_response(
            response=mock_response, message_type=MessageType.GIT, action=GitMessageAction.GET_FILE
        )

        response = client.get(
            "/api/file/repo01/myfile.text",
            headers=client_headers,
        )

        assert response.status_code == 200
        assert response.text == "file content"
