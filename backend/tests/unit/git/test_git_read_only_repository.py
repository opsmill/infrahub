from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from git.exc import GitCommandError
from infrahub_sdk.client import Config, InfrahubClient
from infrahub_sdk.uuidt import UUIDT

from infrahub.exceptions import RepositoryError
from infrahub.git.repository import InfrahubReadOnlyRepository
from infrahub.services import InfrahubServices
from tests.helpers.test_client import dummy_async_request


async def test_new_empty_dir(git_upstream_repo_01: dict[str, str | Path], git_repos_dir: Path) -> None:
    repo = await InfrahubReadOnlyRepository.new(
        id=UUIDT.new(),
        name=git_upstream_repo_01["name"],
        location=str(git_upstream_repo_01["path"]),
        ref="branch01",
        infrahub_branch_name="main",
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
        service=await InfrahubServices.new(),
    )

    assert repo.directory_root.is_dir()
    assert repo.directory_branches.is_dir()
    assert repo.directory_commits.is_dir()
    assert repo.directory_temp.is_dir()


@patch("infrahub.git.base.Repo.clone_from")
@patch("infrahub.git.base.Repo")
async def test_new_invalid_branch(
    mock_repo: MagicMock, mock_clone_from: MagicMock, git_upstream_repo_01: dict[str, str | Path]
) -> None:
    mock_repo_instance = MagicMock()
    mock_repo_instance.git.checkout.side_effect = GitCommandError("checkout", stderr="error: pathspec")
    mock_repo.return_value = mock_repo_instance
    mock_clone_from.return_value = mock_repo_instance
    repo_path = str(git_upstream_repo_01["path"])
    repo_name = git_upstream_repo_01["name"]
    with pytest.raises(
        RepositoryError,
        match=f"The branch non-existent-branch isn't a valid branch for the repository {repo_name} at {repo_path}",
    ):
        await InfrahubReadOnlyRepository.new(
            id=UUIDT.new(),
            name=git_upstream_repo_01["name"],
            location=str(git_upstream_repo_01["path"]),
            ref="non-existent-branch",
            infrahub_branch_name="main",
            client=InfrahubClient(config=Config(requester=dummy_async_request)),
            service=await InfrahubServices.new(),
        )


async def test_get_commit_value(git_repo_01_read_only: InfrahubReadOnlyRepository) -> None:
    repo = git_repo_01_read_only
    assert repo.get_commit_value(branch_name="does_not_matter") == "92700512b5b16c0144f7fd2869669273577f1bd8"
    assert repo.get_commit_value(branch_name="branch02", remote=True) == "92700512b5b16c0144f7fd2869669273577f1bd8"


async def test_get_branches_from_local(git_repo_01_read_only: InfrahubReadOnlyRepository) -> None:
    repo = git_repo_01_read_only

    local_branches = repo.get_branches_from_local()
    assert isinstance(local_branches, dict)
    assert set(local_branches.keys()) == {"main", "branch01"}


async def test_sync_from_remote_new_ref(git_repo_01_read_only: InfrahubReadOnlyRepository) -> None:
    repo = git_repo_01_read_only
    repo.ref = "branch02"
    branch_02_head_commit = "49ac5e2a0f00b5eab6aedfdb19a1ef8127507f72"
    mock_client = AsyncMock(InfrahubClient)
    repo.client = mock_client

    # Mock import_objects_from_files since we're testing git sync, not import functionality
    with patch(
        "infrahub.git.repository.InfrahubReadOnlyRepository.import_objects_from_files", new_callable=AsyncMock
    ):
        await repo.sync_from_remote()

    worktree_commits = {wt.identifier for wt in repo.get_worktrees()}
    assert worktree_commits == {"main", "92700512b5b16c0144f7fd2869669273577f1bd8", branch_02_head_commit}
    mock_client.repository_update_commit.assert_awaited_once_with(
        branch_name="main", repository_id=repo.id, commit=branch_02_head_commit, is_read_only=True
    )


async def test_sync_from_remote_existing_ref(git_repo_01_read_only: InfrahubReadOnlyRepository) -> None:
    repo = git_repo_01_read_only
    repo.ref = "branch01"
    mock_client = AsyncMock(InfrahubClient)
    repo.client = mock_client

    await repo.sync_from_remote()

    worktree_commits = {wt.identifier for wt in repo.get_worktrees()}
    assert worktree_commits == {"main", "92700512b5b16c0144f7fd2869669273577f1bd8"}
    mock_client.repository_update_commit.assert_not_awaited()
