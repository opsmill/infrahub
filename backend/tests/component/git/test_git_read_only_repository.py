from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from git import Repo  # type: ignore[attr-defined]
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


async def test_get_commit_value(
    git_repo_01_read_only: InfrahubReadOnlyRepository, git_upstream_repo_01: dict[str, str | Path]
) -> None:
    repo = git_repo_01_read_only
    upstream = Repo(git_upstream_repo_01["path"])
    branch01_commit = str(upstream.commit("branch01"))
    assert repo.get_commit_value(branch_name="does_not_matter") == branch01_commit
    assert repo.get_commit_value(branch_name="branch02", remote=True) == branch01_commit


async def test_get_commit_value_follows_a_tag_moved_upstream(
    git_upstream_repo_01: dict[str, str | Path], git_repos_dir: Path
) -> None:
    """A copy already holding the tag still resolves where it points now, rather than refusing or keeping the old target."""
    upstream = Repo(git_upstream_repo_01["path"])
    upstream.create_tag("release", ref="main", message="Release")
    repo = await InfrahubReadOnlyRepository.new(
        id=UUIDT.new(),
        name=git_upstream_repo_01["name"],
        location=str(git_upstream_repo_01["path"]),
        ref="release",
        infrahub_branch_name="main",
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
    )
    tagged_before = repo.get_commit_value(branch_name="release", remote=True)

    upstream.git.checkout("main")
    new_file = Path(git_upstream_repo_01["path"]) / "tagged_change.txt"
    new_file.write_text("the release tag moved upstream", encoding="utf-8")
    upstream.index.add(["tagged_change.txt"])
    moved_sha = str(upstream.index.commit("Change the release tag now points at"))
    upstream.create_tag("release", ref=moved_sha, message="Release", force=True)
    assert tagged_before != moved_sha

    assert repo.get_commit_value(branch_name="release", remote=True) == moved_sha


async def test_get_branches_from_local(git_repo_01_read_only: InfrahubReadOnlyRepository) -> None:
    repo = git_repo_01_read_only

    local_branches = repo.get_branches_from_local()
    assert isinstance(local_branches, dict)
    assert set(local_branches.keys()) == {"main", "branch01"}


@patch("infrahub.git.integrator.InfrahubRepositoryIntegrator.import_objects_from_files", new_callable=AsyncMock)
async def test_sync_from_remote_new_ref(
    mock_import_objects: AsyncMock,
    git_repo_01_read_only: InfrahubReadOnlyRepository,
    git_upstream_repo_01: dict[str, str | Path],
) -> None:
    repo = git_repo_01_read_only
    repo.ref = "branch02"
    upstream = Repo(git_upstream_repo_01["path"])
    branch01_commit = str(upstream.commit("branch01"))
    branch02_commit = str(upstream.commit("branch02"))
    mock_client = AsyncMock(InfrahubClient)
    repo.client = mock_client

    await repo.sync_from_remote()

    worktree_commits = {wt.identifier for wt in repo.get_worktrees()}
    assert worktree_commits == {"main", branch01_commit, branch02_commit}
    mock_client.repository_update_commit.assert_awaited_once_with(
        branch_name="main", repository_id=repo.id, commit=branch02_commit, is_read_only=True
    )


async def test_sync_from_remote_existing_ref(
    git_repo_01_read_only: InfrahubReadOnlyRepository, git_upstream_repo_01: dict[str, str | Path]
) -> None:
    repo = git_repo_01_read_only
    repo.ref = "branch01"
    upstream = Repo(git_upstream_repo_01["path"])
    branch01_commit = str(upstream.commit("branch01"))
    mock_client = AsyncMock(InfrahubClient)
    repo.client = mock_client

    await repo.sync_from_remote()

    worktree_commits = {wt.identifier for wt in repo.get_worktrees()}
    assert worktree_commits == {"main", branch01_commit}
    mock_client.repository_update_commit.assert_not_awaited()


@patch("infrahub.git.integrator.InfrahubRepositoryIntegrator.import_objects_from_files", new_callable=AsyncMock)
async def test_update_latest_commit_with_annotated_tag(
    mock_import_objects: AsyncMock,
    git_upstream_repo_01: dict[str, str | Path],
    git_repos_dir: Path,
) -> None:
    """Verify that update_latest_commit stores the commit SHA, not the tag object SHA, for annotated tags."""
    upstream = Repo(git_upstream_repo_01["path"])
    tag_name = "v1.0.0"
    expected_commit = str(upstream.commit("main"))
    upstream.create_tag(tag_name, ref="main", message="Release v1.0.0")

    repo = await InfrahubReadOnlyRepository.new(
        id=UUIDT.new(),
        name=git_upstream_repo_01["name"],
        location=str(git_upstream_repo_01["path"]),
        ref=tag_name,
        infrahub_branch_name="main",
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
        service=await InfrahubServices.new(),
    )
    mock_client = AsyncMock(InfrahubClient)
    repo.client = mock_client

    await repo.update_latest_commit()

    mock_client.repository_update_commit.assert_awaited_with(
        branch_name="main", repository_id=repo.id, commit=expected_commit, is_read_only=True
    )
