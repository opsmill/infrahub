from infrahub.message_bus.events import InfrahubRPCResponse, RPCStatusCode
from infrahub.git import handle_git_rpc_message


async def test_git_rpc_create_successful(git_rpc_repo_add_01):

    response = await handle_git_rpc_message(message=git_rpc_repo_add_01)

    assert isinstance(response, InfrahubRPCResponse)
    assert response.status == RPCStatusCode.CREATED.value


async def test_git_rpc_create_error(git_rpc_repo_add_01, tmpdir):

    git_rpc_repo_add_01.location = f"file:/{tmpdir}"

    response = await handle_git_rpc_message(message=git_rpc_repo_add_01)

    assert isinstance(response, InfrahubRPCResponse)
    assert response.status == RPCStatusCode.BAD_REQUEST.value
