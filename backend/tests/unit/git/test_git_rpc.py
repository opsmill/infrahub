from typing import Any, Dict, Optional

import httpx
import pytest

from infrahub.exceptions import RepositoryError
from infrahub.git import InfrahubRepository, handle_git_rpc_message
from infrahub.message_bus import Meta, messages
from infrahub.message_bus.events import (
    GitMessageAction,
    InfrahubGitRPC,
    InfrahubRPCResponse,
    RPCStatusCode,
)
from infrahub.message_bus.operations import git
from infrahub.message_bus.responses import DiffNamesResponse
from infrahub.services import InfrahubServices
from infrahub_client import UUIDT, Config, InfrahubClient
from infrahub_client.branch import BranchData
from infrahub_client.types import HTTPMethod

# pylint: disable=redefined-outer-name


async def dummy_async_request(
    url: str, method: HTTPMethod, headers: Dict[str, Any], timeout: int, payload: Optional[Dict] = None
) -> httpx.Response:
    """Return an empty response and to pretend that the git commit was updated successfully"""
    return httpx.Response(status_code=200, json={"data": {}}, request=httpx.Request(method="POST", url="http://mock"))


async def test_git_rpc_create_successful(git_upstream_repo_02):
    message = messages.GitRepositoryAdd(
        repository_id=str(UUIDT()),
        repository_name=git_upstream_repo_02["name"],
        location=git_upstream_repo_02["path"],
    )

    client_config = Config(requester=dummy_async_request)
    services = InfrahubServices(client=InfrahubClient(config=client_config))
    await git.repository.add(message=message, service=services)


async def test_git_rpc_create_error(git_upstream_repo_01, tmp_path):
    message = messages.GitRepositoryAdd(
        repository_id=str(UUIDT()),
        repository_name=git_upstream_repo_01["name"],
        location=str(tmp_path),
    )

    client_config = Config(requester=dummy_async_request)
    services = InfrahubServices(client=InfrahubClient(config=client_config))
    with pytest.raises(RepositoryError):
        await git.repository.add(message=message, service=services)


async def test_git_rpc_merge(git_upstream_repo_01, git_repo_01: InfrahubRepository, branch01: BranchData, tmp_path):
    repo = git_repo_01

    await repo.create_branch_in_git(branch_name=branch01.name, branch_id=branch01.id)

    commit_main_before = repo.get_commit_value(branch_name="main")

    message = InfrahubGitRPC(
        action=GitMessageAction.MERGE.value,
        repository_id=str(UUIDT()),
        repository_name=repo.name,
        location=git_upstream_repo_01["path"],
        params={"branch_name": "branch01"},
    )

    response = await handle_git_rpc_message(message=message, client=None)

    commit_main_after = repo.get_commit_value(branch_name="main")

    assert isinstance(response, InfrahubRPCResponse)
    assert response.status == RPCStatusCode.OK
    assert commit_main_before != commit_main_after


async def test_git_rpc_diff(
    git_upstream_repo_01, git_repo_01: InfrahubRepository, branch01: BranchData, branch02: BranchData, tmp_path, helper
):
    repo = git_repo_01

    await repo.create_branch_in_git(branch_name=branch01.name, branch_id=branch01.id)
    await repo.create_branch_in_git(branch_name=branch02.name, branch_id=branch02.id)

    commit_main = repo.get_commit_value(branch_name="main", remote=False)
    commit_branch01 = repo.get_commit_value(branch_name=branch01.name, remote=False)
    commit_branch02 = repo.get_commit_value(branch_name=branch02.name, remote=False)

    # Diff Between Branch01 and Branch02
    correlation_id = str(UUIDT())
    message = messages.GitDiffNamesOnly(
        repository_id=str(UUIDT()),
        repository_name=git_upstream_repo_01["name"],
        first_commit=commit_branch01,
        second_commit=commit_branch02,
        meta=Meta(reply_to="ci-testing", correlation_id=correlation_id),
    )

    bus_simulator = helper.get_message_bus_simulator()
    service = InfrahubServices(client=InfrahubClient(), message_bus=bus_simulator)
    bus_simulator.service = service
    await service.send(message=message)

    assert len(bus_simulator.replies) == 1
    reply = bus_simulator.replies[0]
    result = reply.parse(DiffNamesResponse)
    assert result.files_changed == ["README.md", "test_files/sports.yml"]

    message = messages.GitDiffNamesOnly(
        repository_id=str(UUIDT()),
        repository_name=git_upstream_repo_01["name"],
        first_commit=commit_branch01,
        second_commit=commit_main,
        meta=Meta(reply_to="ci-testing", correlation_id=correlation_id),
    )
    await service.send(message=message)

    assert len(bus_simulator.replies) == 2
    reply = bus_simulator.replies[1]
    result = reply.parse(DiffNamesResponse)
    assert result.files_changed == ["test_files/sports.yml"]
