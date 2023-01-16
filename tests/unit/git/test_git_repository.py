import json
import os
import uuid

import pytest
from git import Repo

from infrahub.exceptions import (
    CheckError,
    FileNotFound,
    RepositoryError,
    TransformError,
)
from infrahub.git import (
    BRANCHES_DIRECTORY_NAME,
    COMMITS_DIRECTORY_NAME,
    TEMPORARY_DIRECTORY_NAME,
    InfrahubRepository,
    RepoFileInformation,
    Worktree,
    extract_repo_file_information,
)
from infrahub_client import MUTATION_COMMIT_UPDATE


async def test_directories_props(git_upstream_repo_01, git_repos_dir):

    repo = await InfrahubRepository.new(
        id=uuid.uuid4(), name=git_upstream_repo_01["name"], location=git_upstream_repo_01["path"]
    )

    assert repo.directory_root == os.path.join(git_repos_dir, git_upstream_repo_01["name"])
    assert repo.directory_branches == os.path.join(git_repos_dir, git_upstream_repo_01["name"], BRANCHES_DIRECTORY_NAME)
    assert repo.directory_commits == os.path.join(git_repos_dir, git_upstream_repo_01["name"], COMMITS_DIRECTORY_NAME)
    assert repo.directory_temp == os.path.join(git_repos_dir, git_upstream_repo_01["name"], TEMPORARY_DIRECTORY_NAME)


async def test_new_empty_dir(git_upstream_repo_01, git_repos_dir):

    repo = await InfrahubRepository.new(
        id=uuid.uuid4(), name=git_upstream_repo_01["name"], location=git_upstream_repo_01["path"]
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
        id=uuid.uuid4(), name=git_upstream_repo_01["name"], location=git_upstream_repo_01["path"]
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
        id=uuid.uuid4(), name=git_upstream_repo_01["name"], location=git_upstream_repo_01["path"]
    )

    # Check if all the directories are present
    assert os.path.isdir(repo.directory_root)
    assert os.path.isdir(repo.directory_branches)
    assert os.path.isdir(repo.directory_commits)
    assert os.path.isdir(repo.directory_temp)


async def test_new_wrong_location(git_upstream_repo_01, git_repos_dir, tmp_path):

    with pytest.raises(RepositoryError) as exc:
        await InfrahubRepository.new(id=uuid.uuid4(), name=git_upstream_repo_01["name"], location=str(tmp_path))

    assert "An error occured with GitRepository" in str(exc.value)


async def test_new_wrong_branch(git_upstream_repo_01, git_repos_dir, tmp_path):

    with pytest.raises(RepositoryError) as exc:
        await InfrahubRepository.new(
            id=uuid.uuid4(),
            name=git_upstream_repo_01["name"],
            location=git_upstream_repo_01["path"],
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

    with pytest.raises(ValueError):
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


async def test_pull_branch(git_repo_04: InfrahubRepository):

    repo = git_repo_04
    await repo.fetch()

    branch_name = "branch01"

    commit1 = repo.get_commit_value(branch_name=branch_name, remote=False)
    commit2 = repo.get_commit_value(branch_name=branch_name, remote=True)
    assert str(commit1) != str(commit2)

    response = await repo.pull(branch_name=branch_name)
    commit11 = repo.get_commit_value(branch_name=branch_name, remote=False)
    assert str(commit11) == str(commit2)
    assert response == str(commit2)

    response = await repo.pull(branch_name=branch_name)
    assert response is True


async def test_pull_branch_conflict(git_repo_06: InfrahubRepository):

    repo = git_repo_06
    await repo.fetch()

    branch_name = "branch01"

    commit1 = repo.get_commit_value(branch_name=branch_name, remote=False)
    commit2 = repo.get_commit_value(branch_name=branch_name, remote=True)
    assert str(commit1) != str(commit2)

    with pytest.raises(RepositoryError) as exc:
        await repo.pull(branch_name=branch_name)

    assert "there is a conflict that must be resolved" in str(exc.value)


async def test_pull_main(git_repo_05: InfrahubRepository):

    repo = git_repo_05
    await repo.fetch()

    branch_name = "main"

    commit1 = repo.get_commit_value(branch_name=branch_name, remote=False)
    commit2 = repo.get_commit_value(branch_name=branch_name, remote=True)
    assert str(commit1) != str(commit2)

    response = await repo.pull(branch_name=branch_name)
    commit11 = repo.get_commit_value(branch_name=branch_name, remote=False)
    assert str(commit11) == str(commit2)
    assert response == str(commit2)


async def test_merge_branch01_into_main(git_repo_01: InfrahubRepository):

    repo = git_repo_01
    await repo.fetch()
    await repo.create_branch_in_git(branch_name="branch01")

    commit_before = repo.get_commit_value(branch_name="main", remote=False)

    response = await repo.merge(source_branch="branch01", dest_branch="main")

    commit_after = repo.get_commit_value(branch_name="main", remote=False)
    assert str(commit_before) != str(commit_after)
    assert response == str(commit_after)


async def test_rebase(git_repo_01: InfrahubRepository):

    repo = git_repo_01
    await repo.fetch()

    await repo.create_branch_in_git(branch_name="branch01")

    # Add a new commit in the main branch to have something to rebase.
    git_repo = repo.get_git_repo_main()
    top_level_files = os.listdir(repo.directory_default)
    first_file = os.path.join(repo.directory_default, top_level_files[0])
    with open(first_file, "a") as file:
        file.write("new line\n")
    git_repo.index.add([top_level_files[0]])
    git_repo.index.commit("Change first file")

    commit_before = repo.get_commit_value(branch_name="branch01", remote=False)
    response = await repo.rebase(branch_name="branch01", source_branch="main")

    commit_after = repo.get_commit_value(branch_name="branch01", remote=False)

    assert str(commit_before) != str(commit_after)
    assert str(response) == str(commit_after)


async def test_sync_no_update(git_repo_02: InfrahubRepository):

    repo = git_repo_02
    await repo.sync()

    assert True


async def test_sync_new_branch(
    client, git_repo_03: InfrahubRepository, httpx_mock, mock_add_branch01_query, mock_list_graphql_query_empty
):

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


async def test_sync_updated_branch(git_repo_04: InfrahubRepository):

    repo = git_repo_04

    # Mock update_commit_value query
    commit = repo.get_commit_value(branch_name="branch01", remote=True)

    await repo.sync()

    assert repo.get_commit_value(branch_name="branch01") == str(commit)


async def test_render_jinja2_template_success(git_repo_jinja: InfrahubRepository):

    repo = git_repo_jinja

    commit_main = repo.get_commit_value(branch_name="main", remote=False)
    commit_branch = repo.get_commit_value(branch_name="branch01", remote=False)
    assert commit_main != commit_branch

    data = {"items": ["consilium", "potum", "album", "magnum"]}
    expected_response = """
consilium
potum
album
magnum
"""
    # Render in both branches based on the commit and validate that we are getting different results
    rendered_tpl_main = await repo.render_jinja2_template(commit=commit_main, location="template01.tpl.j2", data=data)
    assert rendered_tpl_main == expected_response

    rendered_tpl_branch = await repo.render_jinja2_template(
        commit=commit_branch, location="template01.tpl.j2", data=data
    )
    assert rendered_tpl_main != rendered_tpl_branch


async def test_render_jinja2_template_error(git_repo_jinja: InfrahubRepository):

    repo = git_repo_jinja

    commit_main = repo.get_commit_value(branch_name="main", remote=False)

    with pytest.raises(TransformError) as exc:
        await repo.render_jinja2_template(commit=commit_main, location="template02.tpl.j2", data={})

    assert "The innermost block that needs to be closed" in str(exc.value)


async def test_render_jinja2_template_missing(client, git_repo_jinja: InfrahubRepository):

    repo = git_repo_jinja

    commit_main = repo.get_commit_value(branch_name="main", remote=False)

    with pytest.raises(FileNotFound):
        await repo.render_jinja2_template(commit=commit_main, location="notthere.tpl.j2", data={})


async def test_execute_python_check_valid(client, git_repo_checks: InfrahubRepository, mock_gql_query_my_query):

    repo = git_repo_checks
    commit_main = repo.get_commit_value(branch_name="main", remote=False)

    check = await repo.execute_python_check(
        branch_name="main", commit=commit_main, location="check01.py", class_name="Check01", client=client
    )

    assert check.passed is False


async def test_execute_python_check_file_missing(client, git_repo_checks: InfrahubRepository):

    repo = git_repo_checks
    commit_main = repo.get_commit_value(branch_name="main", remote=False)

    with pytest.raises(FileNotFound):
        check = await repo.execute_python_check(
            branch_name="main", commit=commit_main, location="notthere.py", class_name="Check01", client=client
        )


async def test_execute_python_check_class_missing(client, git_repo_checks: InfrahubRepository):

    repo = git_repo_checks
    commit_main = repo.get_commit_value(branch_name="main", remote=False)

    with pytest.raises(CheckError):
        check = await repo.execute_python_check(
            branch_name="main", commit=commit_main, location="check01.py", class_name="Check99", client=client
        )


async def test_find_files(git_repo_jinja: InfrahubRepository):

    repo = git_repo_jinja

    yaml_files = await repo.find_files(extension="yml", branch_name="main")
    assert len(yaml_files) == 2

    yaml_files = await repo.find_files(extension=["yml"], branch_name="main")
    assert len(yaml_files) == 2

    yaml_files = await repo.find_files(extension=["yml", "j2"], branch_name="main")
    assert len(yaml_files) == 4


def test_extract_repo_file_information():

    file_info = extract_repo_file_information(full_filename="/tmp/dir1/dir2/dir3/myfile.py", base_directory="/tmp/dir1")

    assert isinstance(file_info, RepoFileInformation)
    assert file_info.filename == "myfile.py"
    assert file_info.extension == ".py"
    assert file_info.filename_wo_ext == "myfile"
    assert file_info.relative_path == "dir2/dir3"
    assert file_info.absolute_path == "/tmp/dir1/dir2/dir3"
    assert file_info.file_path == "dir2/dir3/myfile.py"

    file_info = extract_repo_file_information(full_filename="/tmp/dir1/dir2/dir3/myfile.py")

    assert isinstance(file_info, RepoFileInformation)
    assert file_info.filename == "myfile.py"
    assert file_info.extension == ".py"
    assert file_info.filename_wo_ext == "myfile"
    assert file_info.relative_path == "/tmp/dir1/dir2/dir3"
    assert file_info.absolute_path == "/tmp/dir1/dir2/dir3"
    assert file_info.file_path == "/tmp/dir1/dir2/dir3/myfile.py"
