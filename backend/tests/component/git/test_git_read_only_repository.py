from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import anyio
import pytest
from git import Repo  # type: ignore[attr-defined]
from git.exc import GitCommandError
from infrahub_sdk.client import Config, InfrahubClient
from infrahub_sdk.uuidt import UUIDT

from infrahub.core.constants import InfrahubKind
from infrahub.exceptions import RepositoryError
from infrahub.git.models import GitReadOnlyRepositoryImportCommit
from infrahub.git.repository import InfrahubReadOnlyRepository
from infrahub.git.tasks import import_read_only_repository_last_commit
from infrahub.services import InfrahubServices
from infrahub.utils import find_first_file_in_directory
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
    assert repo.get_commit_value(branch_name="does_not_matter") == "30e911e25ef9e4fad9f9d00fe05395031f90d460"
    assert repo.get_commit_value(branch_name="branch02", remote=True) == "30e911e25ef9e4fad9f9d00fe05395031f90d460"


async def test_get_branches_from_local(git_repo_01_read_only: InfrahubReadOnlyRepository) -> None:
    repo = git_repo_01_read_only

    local_branches = repo.get_branches_from_local()
    assert isinstance(local_branches, dict)
    assert set(local_branches.keys()) == {"main", "branch01"}


@patch("infrahub.git.integrator.InfrahubRepositoryIntegrator.import_objects_from_files", new_callable=AsyncMock)
async def test_sync_from_remote_new_ref(
    mock_import_objects: AsyncMock, git_repo_01_read_only: InfrahubReadOnlyRepository
) -> None:
    repo = git_repo_01_read_only
    repo.ref = "branch02"
    branch_02_head_commit = "4e2fd98a5fd1fb61dc53150c778e22ee35f26191"
    mock_client = AsyncMock(InfrahubClient)
    repo.client = mock_client

    await repo.sync_from_remote()

    worktree_commits = {wt.identifier for wt in repo.get_worktrees()}
    assert worktree_commits == {"main", "30e911e25ef9e4fad9f9d00fe05395031f90d460", branch_02_head_commit}
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
    assert worktree_commits == {"main", "30e911e25ef9e4fad9f9d00fe05395031f90d460"}
    mock_client.repository_update_commit.assert_not_awaited()


@patch("infrahub.git.tasks.get_client")
@patch("infrahub.git.tasks.add_tags")
@patch("infrahub.git.integrator.InfrahubRepositoryIntegrator.import_objects_from_files", new_callable=AsyncMock)
async def test_import_read_only_repository_last_commit(
    mock_import_objects: AsyncMock,
    mock_add_tags: MagicMock,
    mock_get_client: MagicMock,
    git_repo_01_read_only: InfrahubReadOnlyRepository,
    git_upstream_repo_01: dict[str, str | Path],
) -> None:
    repo = git_repo_01_read_only
    repo.client = AsyncMock()
    repo.ref = "main"
    initial_commit_id = repo.get_commit_value(branch_name="main")

    upstream = Repo(git_upstream_repo_01["path"])
    upstream.git.checkout("main")

    first_file = find_first_file_in_directory(git_upstream_repo_01["path"])
    assert first_file
    async with await anyio.open_file(first_file, mode="a", encoding="utf-8") as file:
        await file.write("new line\n")
    upstream.index.add([first_file])
    upstream.index.commit("Change first file")

    mock_add_tags.return_value = None
    mock_get_client.return_value = AsyncMock(InfrahubClient)

    model = GitReadOnlyRepositoryImportCommit(
        repository_id=str(repo.id),
        repository_name=str(repo.name),
        repository_kind=InfrahubKind.READONLYREPOSITORY,
        infrahub_branch_name="main",
        ref="main",
    )
    await import_read_only_repository_last_commit(model=model)

    new_commit_id = repo.get_commit_value(branch_name="main")
    assert initial_commit_id != new_commit_id
    assert new_commit_id == str(upstream.head.commit)
