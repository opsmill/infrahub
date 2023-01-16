import uuid

from infrahub.message_bus.events import (
    GitMessageAction,
    InfrahubDataMessage,
    InfrahubGitRPC,
    InfrahubMessage,
    InfrahubRPCResponse,
    MessageType,
    RPCStatusCode,
)
from infrahub.message_bus.rpc import InfrahubRpcClientTesting


def test_message_init(incoming_data_message_01):

    message = InfrahubMessage.convert(incoming_data_message_01)

    assert isinstance(message, InfrahubDataMessage)


async def test_rpc_client_testing(rpc_client: InfrahubRpcClientTesting):

    mock_response = InfrahubRPCResponse(status=RPCStatusCode.TOO_EARLY.value)
    await rpc_client.add_response(
        response=mock_response, message_type=MessageType.GIT, action=GitMessageAction.REPO_ADD
    )

    message = InfrahubGitRPC(
        action=GitMessageAction.REPO_ADD.value,
        repository_id=uuid.uuid4(),
        repository_name="my_repo",
        location="/tmp",
    )

    response = await rpc_client.call(message=message)

    assert isinstance(response, InfrahubRPCResponse)
    assert response.status == RPCStatusCode.TOO_EARLY.value
