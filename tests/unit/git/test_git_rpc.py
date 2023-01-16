import uuid

from infrahub.git import InfrahubRepository, handle_git_rpc_message
from infrahub.message_bus.events import (
    GitMessageAction,
    InfrahubGitRPC,
    InfrahubRPCResponse,
    RPCStatusCode,
)

# pylint: disable=W0621


async def test_git_rpc_create_successful(git_upstream_repo_02):

    message = InfrahubGitRPC(
        action=GitMessageAction.REPO_ADD.value,
        repository_id=uuid.uuid4(),
        repository_name=git_upstream_repo_02["name"],
        location=git_upstream_repo_02["path"],
    )

    response = await handle_git_rpc_message(message=message, client=None)

    assert isinstance(response, InfrahubRPCResponse)
    assert response.status == RPCStatusCode.CREATED.value


async def test_git_rpc_create_error(git_upstream_repo_01, tmp_path):

    message = InfrahubGitRPC(
        action=GitMessageAction.REPO_ADD.value,
        repository_id=uuid.uuid4(),
        repository_name=git_upstream_repo_01["name"],
        location=str(tmp_path),
    )

    response = await handle_git_rpc_message(message=message, client=None)

    assert isinstance(response, InfrahubRPCResponse)
    assert response.status == RPCStatusCode.BAD_REQUEST.value


async def test_git_rpc_merge(git_upstream_repo_01, git_repo_01: InfrahubRepository, tmp_path):

    repo = git_repo_01

    await repo.create_branch_in_git(branch_name="branch01")

    commit_main_before = repo.get_commit_value(branch_name="main")

    message = InfrahubGitRPC(
        action=GitMessageAction.MERGE.value,
        repository_id=uuid.uuid4(),
        repository_name=repo.name,
        location=git_upstream_repo_01["path"],
        params={"branch_name": "branch01"},
    )

    response = await handle_git_rpc_message(message=message, client=None)

    commit_main_after = repo.get_commit_value(branch_name="main")

    assert isinstance(response, InfrahubRPCResponse)
    assert response.status == RPCStatusCode.OK.value
    assert commit_main_before != commit_main_after
