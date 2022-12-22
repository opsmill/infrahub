import os
import uuid

from git import Repo
from infrahub.git import InfrahubRepository, Worktree


async def test_directories_props(git_upstream_repo_01, git_repos_dir):

    repo = await InfrahubRepository.new(
        id=uuid.uuid4(), name=git_upstream_repo_01["name"], location=f"file:/{git_upstream_repo_01['path']}"
    )

    assert repo.directory_root == os.path.join(git_repos_dir, git_upstream_repo_01["name"])
    assert repo.directory_branches == os.path.join(git_repos_dir, git_upstream_repo_01["name"], "branches")
    assert repo.directory_commits == os.path.join(git_repos_dir, git_upstream_repo_01["name"], "commits")
    assert repo.directory_temp == os.path.join(git_repos_dir, git_upstream_repo_01["name"], "temp")


async def test_new_empty_dir(git_upstream_repo_01, git_repos_dir):

    repo = await InfrahubRepository.new(
        id=uuid.uuid4(), name=git_upstream_repo_01["name"], location=f"file:/{git_upstream_repo_01['path']}"
    )

    # Check if all the directories are present
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


async def test_get_branches_in_local(git_repo_01: InfrahubRepository):
    repo = git_repo_01

    local_branches = repo.get_branches_from_local()
    assert isinstance(local_branches, dict)
    assert sorted(list(local_branches.keys())) == ["main"]


async def test_get_branches_in_remote(git_repo_01: InfrahubRepository):
    repo = git_repo_01

    remote_branches = repo.get_branches_from_remote()
    assert isinstance(remote_branches, dict)
    assert sorted(list(remote_branches.keys())) == ["branch01", "branch02", "clean-branch", "main"]
