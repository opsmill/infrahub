from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from infrahub_sdk import UUIDT, Config, InfrahubClient
from infrahub_sdk.branch import BranchData
from infrahub_sdk.types import HTTPMethod

from infrahub.exceptions import RepositoryError
from infrahub.git import InfrahubRepository
from infrahub.lock import InfrahubLockRegistry
from infrahub.message_bus import Meta, messages
from infrahub.message_bus.operations import git
from infrahub.message_bus.responses import DiffNamesResponse
from infrahub.services import InfrahubServices

# pylint: disable=redefined-outer-name


async def dummy_async_request(
    url: str, method: HTTPMethod, headers: Dict[str, Any], timeout: int, payload: Optional[Dict] = None
) -> httpx.Response:
    """Return an empty response and to pretend that the git commit was updated successfully"""
    return httpx.Response(status_code=200, json={"data": {}}, request=httpx.Request(method="POST", url="http://mock"))


async def test_git_rpc_create_successful(git_upstream_repo_02):
    repo_id = str(UUIDT())
    branch_name = "b12"
    message = messages.GitRepositoryAdd(
        repository_id=repo_id,
        repository_name=git_upstream_repo_02["name"],
        location=git_upstream_repo_02["path"],
        default_branch_name=branch_name,
    )
    client_config = Config(requester=dummy_async_request)
    client = InfrahubClient(config=client_config)
    services = InfrahubServices(client=client)
    with (
        patch(
            "infrahub.message_bus.operations.git.repository.InfrahubRepository", spec=InfrahubRepository
        ) as mock_repo_class,
        patch("infrahub.message_bus.operations.git.repository.lock") as mock_infra_lock,
    ):
        mock_repo = AsyncMock(spec=InfrahubRepository)
        mock_repo.default_branch_name = branch_name
        mock_repo_class.new.return_value = mock_repo
        mock_infra_lock.registry = AsyncMock(spec=InfrahubLockRegistry)

        await git.repository.add(message=message, service=services)

        mock_infra_lock.registry.get.assert_called_once_with(name=git_upstream_repo_02["name"], namespace="repository")
        mock_repo_class.new.assert_awaited_once_with(
            id=repo_id, name=git_upstream_repo_02["name"], location=git_upstream_repo_02["path"], client=client
        )
        mock_repo.import_objects_from_files.assert_awaited_once_with(branch_name=branch_name)
        mock_repo.sync.assert_awaited_once_with()


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


async def test_git_rpc_merge(
    git_upstream_repo_01, git_repo_01: InfrahubRepository, branch01: BranchData, tmp_path, helper
):
    repo = git_repo_01

    await repo.create_branch_in_git(branch_name=branch01.name, branch_id=branch01.id)

    commit_main_before = repo.get_commit_value(branch_name="main")

    message = messages.GitRepositoryMerge(
        repository_id=str(UUIDT()), repository_name=repo.name, source_branch="branch01", destination_branch="main"
    )

    client_config = Config(requester=dummy_async_request)
    bus_simulator = helper.get_message_bus_simulator()
    service = InfrahubServices(client=InfrahubClient(config=client_config), message_bus=bus_simulator)
    bus_simulator.service = service
    await service.send(message=message)

    commit_main_after = repo.get_commit_value(branch_name="main")

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
