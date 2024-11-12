from pathlib import Path
from unittest.mock import AsyncMock

from infrahub_sdk.client import Config, InfrahubClient
from infrahub_sdk.uuidt import UUIDT

from infrahub.git.repository import InfrahubReadOnlyRepository
from tests.helpers.test_client import dummy_async_request


async def test_new_empty_dir(git_upstream_repo_01: dict[str, str | Path], git_repos_dir: Path):
    repo = await InfrahubReadOnlyRepository.new(
        id=UUIDT.new(),
        name=git_upstream_repo_01["name"],
        location=str(git_upstream_repo_01["path"]),
        ref="branch01",
        infrahub_branch_name="main",
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
    )

    assert repo.directory_root.is_dir()
    assert repo.directory_branches.is_dir()
    assert repo.directory_commits.is_dir()
    assert repo.directory_temp.is_dir()


async def test_get_commit_value(git_repo_01_read_only: InfrahubReadOnlyRepository):
    repo = git_repo_01_read_only
    assert repo.get_commit_value(branch_name="does_not_matter") == "92700512b5b16c0144f7fd2869669273577f1bd8"
    assert repo.get_commit_value(branch_name="branch02", remote=True) == "92700512b5b16c0144f7fd2869669273577f1bd8"


async def test_get_branches_from_local(git_repo_01_read_only: InfrahubReadOnlyRepository):
    repo = git_repo_01_read_only

    local_branches = repo.get_branches_from_local()
    assert isinstance(local_branches, dict)
    assert set(local_branches.keys()) == {"main", "branch01"}


async def test_sync_from_remote_new_ref(git_repo_01_read_only: InfrahubReadOnlyRepository):
    repo = git_repo_01_read_only
    repo.ref = "branch02"
    branch_02_head_commit = "49ac5e2a0f00b5eab6aedfdb19a1ef8127507f72"
    mock_client = AsyncMock(InfrahubClient)
    repo.client = mock_client

    await repo.sync_from_remote()

    worktree_commits = {wt.identifier for wt in repo.get_worktrees()}
    assert worktree_commits == {"main", "92700512b5b16c0144f7fd2869669273577f1bd8", branch_02_head_commit}
    mock_client.repository_update_commit.assert_awaited_once_with(
        branch_name="main", repository_id=repo.id, commit=branch_02_head_commit, is_read_only=True
    )


async def test_sync_from_remote_existing_ref(git_repo_01_read_only: InfrahubReadOnlyRepository):
    repo = git_repo_01_read_only
    repo.ref = "branch01"
    mock_client = AsyncMock(InfrahubClient)
    repo.client = mock_client

    await repo.sync_from_remote()

    worktree_commits = {wt.identifier for wt in repo.get_worktrees()}
    assert worktree_commits == {"main", "92700512b5b16c0144f7fd2869669273577f1bd8"}
    mock_client.repository_update_commit.assert_not_awaited()
