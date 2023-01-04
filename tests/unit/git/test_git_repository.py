import os
import uuid
import pytest

from git import Repo
from infrahub.git import (
    InfrahubRepository,
    Worktree,
    COMMITS_DIRECTORY_NAME,
    BRANCHES_DIRECTORY_NAME,
    TEMPORARY_DIRECTORY_NAME,
)
from infrahub.exceptions import RepositoryError


async def test_directories_props(git_upstream_repo_01, git_repos_dir):

    repo = await InfrahubRepository.new(
        id=uuid.uuid4(), name=git_upstream_repo_01["name"], location=f"file:/{git_upstream_repo_01['path']}"
    )

    assert repo.directory_root == os.path.join(git_repos_dir, git_upstream_repo_01["name"])
    assert repo.directory_branches == os.path.join(git_repos_dir, git_upstream_repo_01["name"], BRANCHES_DIRECTORY_NAME)
    assert repo.directory_commits == os.path.join(git_repos_dir, git_upstream_repo_01["name"], COMMITS_DIRECTORY_NAME)
    assert repo.directory_temp == os.path.join(git_repos_dir, git_upstream_repo_01["name"], TEMPORARY_DIRECTORY_NAME)


async def test_new_empty_dir(git_upstream_repo_01, git_repos_dir):

    repo = await InfrahubRepository.new(
        id=uuid.uuid4(), name=git_upstream_repo_01["name"], location=f"file:/{git_upstream_repo_01['path']}"
    )

    # Check if all the directories are present
    assert os.path.isdir(repo.directory_root)
    assert os.path.isdir(repo.directory_branches)
    assert os.path.isdir(repo.directory_commits)
    assert os.path.isdir(repo.directory_temp)


async def test_new_existing_directory(git_upstream_repo_01, git_repos_dir):

    # Create a directory and a file where the repository will be created
    os.mkdir(os.path.join(git_repos_dir, git_upstream_repo_01["name"]))
    open(os.path.join(git_repos_dir, git_upstream_repo_01["name"], "file1.txt"), mode="w").close()

    repo = await InfrahubRepository.new(
        id=uuid.uuid4(), name=git_upstream_repo_01["name"], location=f"file:/{git_upstream_repo_01['path']}"
    )

    # Check if all the directories are present
    assert os.path.isdir(repo.directory_root)
    assert os.path.isdir(repo.directory_branches)
    assert os.path.isdir(repo.directory_commits)
    assert os.path.isdir(repo.directory_temp)


async def test_new_existing_file(git_upstream_repo_01, git_repos_dir):

    # Create a file where the repository will be created
    open(os.path.join(git_repos_dir, git_upstream_repo_01["name"]), mode="w").close()

    repo = await InfrahubRepository.new(
        id=uuid.uuid4(), name=git_upstream_repo_01["name"], location=f"file:/{git_upstream_repo_01['path']}"
    )

    # Check if all the directories are present
    assert os.path.isdir(repo.directory_root)
    assert os.path.isdir(repo.directory_branches)
    assert os.path.isdir(repo.directory_commits)
    assert os.path.isdir(repo.directory_temp)


async def test_new_wrong_location(git_upstream_repo_01, git_repos_dir, tmpdir):

    with pytest.raises(RepositoryError) as exc:
        repo = await InfrahubRepository.new(
            id=uuid.uuid4(), name=git_upstream_repo_01["name"], location=f"file:/{tmpdir}"
        )

    assert "Unable to clone" in str(exc.value)


async def test_new_wrong_branch(git_upstream_repo_01, git_repos_dir, tmpdir):

    with pytest.raises(RepositoryError) as exc:
        repo = await InfrahubRepository.new(
            id=uuid.uuid4(),
            name=git_upstream_repo_01["name"],
            location=f"file:/{git_upstream_repo_01['path']}",
            default_branch_name="notvalid",
        )

    assert "isn't a valid branch" in str(exc.value)


async def test_init_existing_repository(git_repo_01: InfrahubRepository):

    repo = await InfrahubRepository.init(id=git_repo_01.id, name=git_repo_01.name)

    # Check if all the directories are present
    assert repo.has_origin is True
    assert os.path.isdir(repo.directory_root)
    assert os.path.isdir(repo.directory_branches)
    assert os.path.isdir(repo.directory_commits)
    assert os.path.isdir(repo.directory_temp)


async def test_get_git_repo_main(git_repo_01: InfrahubRepository):
    repo = git_repo_01

    git_repo = repo.get_git_repo_main()

    assert isinstance(git_repo, Repo)


async def test_get_worktrees(git_repo_01: InfrahubRepository):
    repo = git_repo_01

    worktrees = repo.get_worktrees()

    assert len(worktrees) == 2
    assert isinstance(worktrees[0], Worktree)
    assert worktrees[0].directory.startswith(repo.directory_root)


async def test_get_branches_from_local(git_repo_01: InfrahubRepository):
    repo = git_repo_01

    local_branches = repo.get_branches_from_local()
    assert isinstance(local_branches, dict)
    assert sorted(list(local_branches.keys())) == ["main"]


async def test_get_branches_from_remote(git_repo_01: InfrahubRepository):
    repo = git_repo_01

    remote_branches = repo.get_branches_from_remote()
    assert isinstance(remote_branches, dict)
    assert sorted(list(remote_branches.keys())) == ["branch01", "branch02", "clean-branch", "main"]


async def test_get_branches_from_graph(
    git_repo_01: InfrahubRepository, mock_branches_list_query, mock_repositories_query
):
    repo = git_repo_01

    branches = await repo.get_branches_from_graph()
    assert isinstance(branches, dict)
    assert len(branches) == 2
    assert branches["cr1234"].commit == "bbbbbbbbbbbbbbbbbbbb"
