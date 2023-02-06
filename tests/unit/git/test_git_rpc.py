import uuid

from infrahub.git import InfrahubRepository, handle_git_rpc_message
from infrahub.message_bus.events import (
    GitMessageAction,
    InfrahubGitRPC,
    InfrahubRPCResponse,
    RPCStatusCode,
)

# pylint: disable=redefined-outer-name


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


async def test_git_rpc_diff(git_upstream_repo_01, git_repo_01: InfrahubRepository, tmp_path):

    repo = git_repo_01

    await repo.create_branch_in_git(branch_name="branch01")
    await repo.create_branch_in_git(branch_name="branch02")

    commit_main = repo.get_commit_value(branch_name="main", remote=False)
    commit_branch01 = repo.get_commit_value(branch_name="branch01", remote=False)
    commit_branch02 = repo.get_commit_value(branch_name="branch02", remote=False)

    # Diff Between Branch01 and Branch02
    message = InfrahubGitRPC(
        action=GitMessageAction.DIFF.value,
        repository_id=uuid.uuid4(),
        repository_name=repo.name,
        location=git_upstream_repo_01["path"],
        params={"first_commit": commit_branch01, "second_commit": commit_branch02},
    )

    response = await handle_git_rpc_message(message=message, client=None)

    assert isinstance(response, InfrahubRPCResponse)
    assert response.status == RPCStatusCode.OK.value
    assert response.response.get("files_changed") == ["README.md", "test_files/sports.yml"]

    # Diff Between Branch01 and Main
    message = InfrahubGitRPC(
        action=GitMessageAction.DIFF.value,
        repository_id=uuid.uuid4(),
        repository_name=repo.name,
        location=git_upstream_repo_01["path"],
        params={"first_commit": commit_branch01, "second_commit": commit_main},
    )

    response = await handle_git_rpc_message(message=message, client=None)

    assert isinstance(response, InfrahubRPCResponse)
    assert response.status == RPCStatusCode.OK.value
    assert response.response.get("files_changed") == ["test_files/sports.yml"]
