import uuid

import pytest

from infrahub.git import handle_git_rpc_message
from infrahub.message_bus.events import (
    GitMessageAction,
    InfrahubGitRPC,
    InfrahubRPCResponse,
    RPCStatusCode,
)

# pylint: disable=W0621

@pytest.fixture
def git_rpc_repo_add_01(git_upstream_repo_01):

    return InfrahubGitRPC(
        action=GitMessageAction.REPO_ADD.value,
        repository_id=uuid.uuid4(),
        repository_name=git_upstream_repo_01["name"],
        location=f"file:/{git_upstream_repo_01['path']}",
    )


@pytest.fixture
def git_rpc_repo_add_02(git_upstream_repo_02):

    return InfrahubGitRPC(
        action=GitMessageAction.REPO_ADD.value,
        repository_id=uuid.uuid4(),
        repository_name=git_upstream_repo_02["name"],
        location=f"file:/{git_upstream_repo_02['path']}",
    )


async def test_git_rpc_create_successful(git_rpc_repo_add_02):

    response = await handle_git_rpc_message(message=git_rpc_repo_add_02, client=None)

    assert isinstance(response, InfrahubRPCResponse)
    assert response.status == RPCStatusCode.CREATED.value


async def test_git_rpc_create_error(git_rpc_repo_add_01, tmpdir):

    git_rpc_repo_add_01.location = f"file:/{tmpdir}"

    response = await handle_git_rpc_message(message=git_rpc_repo_add_01, client=None)

    assert isinstance(response, InfrahubRPCResponse)
    assert response.status == RPCStatusCode.BAD_REQUEST.value
