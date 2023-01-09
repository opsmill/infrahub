import os
import uuid
import pytest
import json

from git import Repo
from infrahub.git import (
    InfrahubRepository,
    Worktree,
    COMMITS_DIRECTORY_NAME,
    BRANCHES_DIRECTORY_NAME,
    TEMPORARY_DIRECTORY_NAME,
    MUTATION_COMMIT_UPDATE,
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
    assert worktrees[0].identifier == "main"
    assert len(worktrees[1].identifier) == 40


async def test_has_worktree(git_repo_01: InfrahubRepository):
    repo = git_repo_01

    assert not repo.has_worktree("notvalid")
    assert repo.has_worktree("main")


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
    git_repo_01_w_client: InfrahubRepository, mock_branches_list_query, mock_repositories_query
):
    repo = git_repo_01_w_client

    branches = await repo.get_branches_from_graph()
    assert isinstance(branches, dict)
    assert len(branches) == 2
    assert branches["cr1234"].commit == "bbbbbbbbbbbbbbbbbbbb"


async def test_get_commit_value(git_repo_01: InfrahubRepository):

    repo = git_repo_01
    assert repo.get_commit_value(branch_name="main", remote=True) == "0b341c0c64122bb2a7b208f7a9452146685bc7dd"
    assert repo.get_commit_value(branch_name="branch01", remote=True) == "92700512b5b16c0144f7fd2869669273577f1bd8"
    assert repo.get_commit_value(branch_name="branch02", remote=True) == "49ac5e2a0f00b5eab6aedfdb19a1ef8127507f72"

    with pytest.raises(ValueError) as exc:
        repo.get_commit_value(branch_name="branch01", remote=False)


async def test_compare_remote_local_new_branches(git_repo_01: InfrahubRepository):

    repo = git_repo_01
    new_branches, updated_branches = await repo.compare_local_remote()

    assert new_branches == ["branch01", "branch02", "clean-branch"]
    assert updated_branches == []


async def test_compare_remote_local_no_diff(git_repo_02: InfrahubRepository):

    repo = git_repo_02
    new_branches, updated_branches = await repo.compare_local_remote()

    assert new_branches == []
    assert updated_branches == []


async def test_create_branch_in_git_present_remote(git_repo_01: InfrahubRepository):

    repo = git_repo_01
    await repo.create_branch_in_git(branch_name="branch01")
    worktrees = repo.get_worktrees()

    assert repo.get_commit_value(branch_name="branch01") == "92700512b5b16c0144f7fd2869669273577f1bd8"
    assert len(worktrees) == 4


async def test_create_branch_in_git_not_in_remote(git_repo_01: InfrahubRepository):

    repo = git_repo_01
    await repo.create_branch_in_git(branch_name="branch99")
    worktrees = repo.get_worktrees()

    assert repo.get_commit_value(branch_name="branch99") == "0b341c0c64122bb2a7b208f7a9452146685bc7dd"
    assert len(worktrees) == 3


async def test_sync_no_update(git_repo_02: InfrahubRepository):

    repo = git_repo_02
    await repo.sync()

    assert True


async def test_sync_new_branches(client, git_repo_03: InfrahubRepository, httpx_mock, mock_add_branch01_query):

    repo = git_repo_03

    await repo.fetch()
    # Mock update_commit_value query
    commit = repo.get_commit_value(branch_name="branch01", remote=True)

    response = {"data": {"repository_update": {"ok": True, "object": {"commit": {"value": str(commit)}}}}}
    variables = {"repository_id": str(repo.id), "commit": str(commit)}
    request_content = json.dumps({"query": MUTATION_COMMIT_UPDATE, "variables": variables}).encode()
    httpx_mock.add_response(method="POST", json=response, match_content=request_content)

    repo.client = client
    await repo.sync()
    worktrees = repo.get_worktrees()

    assert repo.get_commit_value(branch_name="branch01") == "92700512b5b16c0144f7fd2869669273577f1bd8"
    assert len(worktrees) == 4
