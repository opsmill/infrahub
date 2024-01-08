import os

import pytest
from git import Repo
from infrahub_sdk import UUIDT, InfrahubNode
from infrahub_sdk.branch import BranchData

from infrahub.exceptions import (
    CheckError,
    CommitNotFoundError,
    FileNotFound,
    RepositoryError,
    TransformError,
)
from infrahub.git import (
    BRANCHES_DIRECTORY_NAME,
    COMMITS_DIRECTORY_NAME,
    TEMPORARY_DIRECTORY_NAME,
    ArtifactGenerateResult,
    CheckDefinitionInformation,
    GraphQLQueryInformation,
    InfrahubRepository,
    RepoFileInformation,
    Worktree,
    extract_repo_file_information,
)
from infrahub.utils import find_first_file_in_directory


async def test_directories_props(git_upstream_repo_01, git_repos_dir):
    repo = await InfrahubRepository.new(
        id=UUIDT.new(), name=git_upstream_repo_01["name"], location=git_upstream_repo_01["path"]
    )

    assert repo.directory_root == os.path.join(git_repos_dir, git_upstream_repo_01["name"])
    assert repo.directory_branches == os.path.join(git_repos_dir, git_upstream_repo_01["name"], BRANCHES_DIRECTORY_NAME)
    assert repo.directory_commits == os.path.join(git_repos_dir, git_upstream_repo_01["name"], COMMITS_DIRECTORY_NAME)
    assert repo.directory_temp == os.path.join(git_repos_dir, git_upstream_repo_01["name"], TEMPORARY_DIRECTORY_NAME)


async def test_new_empty_dir(git_upstream_repo_01, git_repos_dir):
    repo = await InfrahubRepository.new(
        id=UUIDT.new(), name=git_upstream_repo_01["name"], location=git_upstream_repo_01["path"]
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
        id=UUIDT.new(), name=git_upstream_repo_01["name"], location=git_upstream_repo_01["path"]
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
        id=UUIDT.new(), name=git_upstream_repo_01["name"], location=git_upstream_repo_01["path"]
    )

    # Check if all the directories are present
    assert os.path.isdir(repo.directory_root)
    assert os.path.isdir(repo.directory_branches)
    assert os.path.isdir(repo.directory_commits)
    assert os.path.isdir(repo.directory_temp)


async def test_new_wrong_location(git_upstream_repo_01, git_repos_dir, tmp_path):
    with pytest.raises(RepositoryError) as exc:
        await InfrahubRepository.new(id=UUIDT.new(), name=git_upstream_repo_01["name"], location=str(tmp_path))

    assert "An error occured with GitRepository" in str(exc.value)


async def test_new_wrong_branch(git_upstream_repo_01, git_repos_dir, tmp_path):
    with pytest.raises(RepositoryError) as exc:
        await InfrahubRepository.new(
            id=UUIDT.new(),
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


async def test_create_commit_worktree(git_repo_01: InfrahubRepository):
    repo = git_repo_01
    git_repo = repo.get_git_repo_main()

    # Modify the first file in the main branch to create a new commit
    first_file = find_first_file_in_directory(repo.directory_default)
    with open(os.path.join(repo.directory_default, first_file), "a") as file:
        file.write("new line\n")
    git_repo.index.add([first_file])
    git_repo.index.commit("Change first file")

    commit = repo.get_commit_value(branch_name="main")

    assert repo.has_worktree(identifier=commit) is False
    assert isinstance(repo.create_commit_worktree(commit=commit), Worktree)
    assert repo.has_worktree(identifier=commit) is True
    assert repo.create_commit_worktree(commit=commit) is False


async def test_create_commit_worktree_wrong_commit(git_repo_01: InfrahubRepository):
    repo = git_repo_01
    repo.get_git_repo_main()

    commit = "ffff1c0c64122bb2a7b208f7a9452146685bc7dd"

    with pytest.raises(CommitNotFoundError):
        repo.create_commit_worktree(commit=commit)


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


async def test_get_commit_worktree(git_repo_01: InfrahubRepository):
    repo = git_repo_01
    git_repo = repo.get_git_repo_main()

    # Modify the first file in the main branch to create a new commit
    first_file = find_first_file_in_directory(repo.directory_default)
    with open(os.path.join(repo.directory_default, first_file), "a") as file:
        file.write("new line\n")
    git_repo.index.add([first_file])
    git_repo.index.commit("Change first file")

    commit = repo.get_commit_value(branch_name="main")

    assert repo.has_worktree(identifier=commit) is False
    worktree = repo.get_commit_worktree(commit=commit)
    assert isinstance(worktree, Worktree)
    assert repo.has_worktree(identifier=commit) is True


async def test_get_branch_worktree(git_repo_01: InfrahubRepository, branch99: BranchData):
    repo = git_repo_01
    git_repo = repo.get_git_repo_main()

    git_repo.git.branch(branch99.name)

    assert repo.has_worktree(identifier=branch99.name) is False
    repo.create_branch_worktree(branch_name=branch99.name, branch_id=branch99.id)
    assert repo.has_worktree(identifier=branch99.name)


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


async def test_create_branch_in_git_present_remote(git_repo_01: InfrahubRepository, branch01: BranchData):
    repo = git_repo_01
    await repo.create_branch_in_git(branch_name=branch01.name, branch_id=branch01.id)
    worktrees = repo.get_worktrees()

    assert repo.get_commit_value(branch_name=branch01.name) == "92700512b5b16c0144f7fd2869669273577f1bd8"
    assert len(worktrees) == 4


async def test_create_branch_in_git_not_in_remote(git_repo_01: InfrahubRepository, branch99: BranchData):
    repo = git_repo_01
    await repo.create_branch_in_git(branch_name=branch99.name, branch_id=branch99.id)
    worktrees = repo.get_worktrees()

    assert repo.get_commit_value(branch_name=branch99.name) == "0b341c0c64122bb2a7b208f7a9452146685bc7dd"
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


async def test_merge_branch01_into_main(git_repo_01: InfrahubRepository, branch01: BranchData):
    repo = git_repo_01
    await repo.fetch()
    await repo.create_branch_in_git(branch_name=branch01.name, branch_id=branch01.id)

    commit_before = repo.get_commit_value(branch_name="main", remote=False)

    response = await repo.merge(source_branch=branch01.name, dest_branch="main")

    commit_after = repo.get_commit_value(branch_name="main", remote=False)
    assert str(commit_before) != str(commit_after)
    assert response == str(commit_after)


async def test_rebase(git_repo_01: InfrahubRepository, branch01: BranchData):
    repo = git_repo_01
    await repo.fetch()

    await repo.create_branch_in_git(branch_name=branch01.name, branch_id=branch01.id)

    # Add a new commit in the main branch to have something to rebase.
    git_repo = repo.get_git_repo_main()
    first_file = find_first_file_in_directory(repo.directory_default)
    with open(os.path.join(repo.directory_default, first_file), "a") as file:
        file.write("new line\n")
    git_repo.index.add([first_file])
    git_repo.index.commit("Change first file")

    commit_before = repo.get_commit_value(branch_name=branch01.name, remote=False)
    response = await repo.rebase(branch_name=branch01.name, source_branch="main")

    commit_after = repo.get_commit_value(branch_name=branch01.name, remote=False)

    assert str(commit_before) != str(commit_after)
    assert str(response) == str(commit_after)


async def test_sync_no_update(git_repo_02: InfrahubRepository):
    repo = git_repo_02
    await repo.sync()

    assert True


async def test_sync_new_branch(client, git_repo_03: InfrahubRepository, httpx_mock, mock_add_branch01_query):
    repo = git_repo_03

    await repo.fetch()
    # Mock update_commit_value query
    commit = repo.get_commit_value(branch_name="branch01", remote=True)

    response = {"data": {"repository_update": {"ok": True, "object": {"commit": {"value": str(commit)}}}}}
    httpx_mock.add_response(
        method="POST", json=response, match_headers={"X-Infrahub-Tracker": "mutation-repository-update-commit"}
    )

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
        await repo.execute_python_check(
            branch_name="main", commit=commit_main, location="notthere.py", class_name="Check01", client=client
        )


async def test_execute_python_check_class_missing(client, git_repo_checks: InfrahubRepository):
    repo = git_repo_checks
    commit_main = repo.get_commit_value(branch_name="main", remote=False)

    with pytest.raises(CheckError):
        await repo.execute_python_check(
            branch_name="main", commit=commit_main, location="check01.py", class_name="Check99", client=client
        )


async def test_execute_python_transform_w_data(client, git_repo_transforms: InfrahubRepository):
    repo = git_repo_transforms
    commit_main = repo.get_commit_value(branch_name="main", remote=False)

    data = {"key1": "value1", "key2": "value2"}
    expected_data = {"KEY1": "value1", "KEY2": "value2"}

    result = await repo.execute_python_transform(
        branch_name="main",
        data=data,
        commit=commit_main,
        location="transform01.py::Transform01",
        client=client,
    )

    assert result == expected_data


async def test_execute_python_transform_w_query(
    client, git_repo_transforms: InfrahubRepository, mock_gql_query_my_query
):
    repo = git_repo_transforms
    commit_main = repo.get_commit_value(branch_name="main", remote=False)

    expected_data = {"MOCK": []}

    result = await repo.execute_python_transform(
        branch_name="main", commit=commit_main, location="transform01.py::Transform01", client=client
    )

    assert result == expected_data


async def test_artifact_generate_python_new(
    client,
    git_repo_transforms_w_client: InfrahubRepository,
    transformation_node_01: InfrahubNode,
    artifact_definition_node_01: InfrahubNode,
    gql_query_node_03: InfrahubNode,
    car_node_01: InfrahubNode,
    artifact_node_01: InfrahubNode,
    mock_gql_query_03,
    mock_upload_content,
    mock_update_artifact,
):
    repo = git_repo_transforms_w_client
    commit_main = repo.get_commit_value(branch_name="main", remote=False)

    result = await repo.artifact_generate(
        branch_name="main",
        commit=commit_main,
        artifact=artifact_node_01,
        target=car_node_01,
        definition=artifact_definition_node_01,
        transformation=transformation_node_01,
        query=gql_query_node_03,
    )

    expected_data = ArtifactGenerateResult(
        changed=True,
        checksum="e889b9fab24aab3b23ea01d5342b514a",
        storage_id="ee04f134-a68c-4158-a3c8-3ba5e9cc0c9a",
        artifact_id=result.artifact_id,
    )
    assert result == expected_data


async def test_artifact_generate_python_existing_same(
    client,
    git_repo_transforms_w_client: InfrahubRepository,
    transformation_node_01: InfrahubNode,
    artifact_definition_node_01: InfrahubNode,
    gql_query_node_03: InfrahubNode,
    car_node_01: InfrahubNode,
    artifact_node_02: InfrahubNode,
    mock_gql_query_03,
):
    repo = git_repo_transforms_w_client
    commit_main = repo.get_commit_value(branch_name="main", remote=False)

    result = await repo.artifact_generate(
        branch_name="main",
        commit=commit_main,
        artifact=artifact_node_02,
        target=car_node_01,
        definition=artifact_definition_node_01,
        transformation=transformation_node_01,
        query=gql_query_node_03,
    )

    expected_data = ArtifactGenerateResult(
        changed=False,
        checksum="e889b9fab24aab3b23ea01d5342b514a",
        storage_id="13c8914b-0ac0-4c8c-83ec-a79a1f8ad483",
        artifact_id=artifact_node_02.id,
    )
    assert result == expected_data


async def test_artifact_generate_python_existing_different(
    client,
    git_repo_transforms_w_client: InfrahubRepository,
    transformation_node_01: InfrahubNode,
    artifact_definition_node_01: InfrahubNode,
    gql_query_node_03: InfrahubNode,
    artifact_node_01: InfrahubNode,
    car_node_01: InfrahubNode,
    mock_gql_query_03,
    mock_upload_content,
    mock_update_artifact,
):
    repo = git_repo_transforms_w_client
    commit_main = repo.get_commit_value(branch_name="main", remote=False)

    result = await repo.artifact_generate(
        branch_name="main",
        commit=commit_main,
        artifact=artifact_node_01,
        target=car_node_01,
        definition=artifact_definition_node_01,
        transformation=transformation_node_01,
        query=gql_query_node_03,
    )

    expected_data = ArtifactGenerateResult(
        changed=True,
        checksum="e889b9fab24aab3b23ea01d5342b514a",
        storage_id="ee04f134-a68c-4158-a3c8-3ba5e9cc0c9a",
        artifact_id=artifact_node_01.id,
    )
    assert result == expected_data


async def test_artifact_generate_jinja2_new(
    client,
    git_repo_jinja_w_client: InfrahubRepository,
    transformation_node_02: InfrahubNode,
    artifact_definition_node_02: InfrahubNode,
    gql_query_node_03: InfrahubNode,
    car_node_01: InfrahubNode,
    artifact_node_01: InfrahubNode,
    mock_gql_query_04,
    mock_update_artifact,
    mock_upload_content,
):
    repo = git_repo_jinja_w_client
    commit_main = repo.get_commit_value(branch_name="main", remote=False)

    result = await repo.artifact_generate(
        branch_name="main",
        commit=commit_main,
        artifact=artifact_node_01,
        target=car_node_01,
        definition=artifact_definition_node_02,
        transformation=transformation_node_02,
        query=gql_query_node_03,
    )

    expected_data = ArtifactGenerateResult(
        changed=True,
        checksum="68b329da9893e34099c7d8ad5cb9c940",
        storage_id="ee04f134-a68c-4158-a3c8-3ba5e9cc0c9a",
        artifact_id=artifact_node_01.id,
    )
    assert result == expected_data


async def test_execute_python_transform_file_missing(client, git_repo_transforms: InfrahubRepository):
    repo = git_repo_transforms
    commit_main = repo.get_commit_value(branch_name="main", remote=False)

    with pytest.raises(FileNotFound):
        await repo.execute_python_transform(
            branch_name="main", commit=commit_main, location="transform99.py::Transform01", client=client
        )


async def test_find_files(git_repo_jinja: InfrahubRepository):
    repo = git_repo_jinja

    with pytest.raises(ValueError):
        await repo.find_files(extension="yml")

    yaml_files = await repo.find_files(extension="yml", branch_name="main")
    assert len(yaml_files) == 2

    yaml_files = await repo.find_files(extension=["yml"], branch_name="main")
    assert len(yaml_files) == 2

    yaml_files = await repo.find_files(extension=["yml", "j2"], branch_name="main")
    assert len(yaml_files) == 4

    yaml_files = await repo.find_files(extension="yml", directory="test_files", branch_name="main")
    assert len(yaml_files) == 2

    yaml_files = await repo.find_files(extension="yml", directory="notpresent", branch_name="main")
    assert len(yaml_files) == 0


async def test_find_files_by_commit(git_repo_jinja: InfrahubRepository):
    repo = git_repo_jinja

    commit = repo.get_commit_value(branch_name="main")

    yaml_files = await repo.find_files(extension="yml", commit=commit)
    assert len(yaml_files) == 2

    yaml_files = await repo.find_files(extension=["yml"], branch_name=commit)
    assert len(yaml_files) == 2

    yaml_files = await repo.find_files(extension=["yml", "j2"], branch_name=commit)
    assert len(yaml_files) == 4


async def test_find_graphql_queries(git_repo_10: InfrahubRepository):
    repo = git_repo_10

    commit = repo.get_commit_value(branch_name="main")

    queries = await repo.find_graphql_queries(commit=commit)
    assert len(queries) == 5
    assert isinstance(queries[0], GraphQLQueryInformation)


async def test_calculate_diff_between_commits(
    git_repo_01: InfrahubRepository, branch01: BranchData, branch02: BranchData
):
    repo = git_repo_01

    await repo.create_branch_in_git(branch_name=branch01.name, branch_id=branch01.id)
    await repo.create_branch_in_git(branch_name=branch02.name, branch_id=branch02.id)

    worktree = repo.get_worktree(identifier=branch01.name)
    git_repo = repo.get_git_repo_worktree(identifier=branch01.name)

    # Add a file
    new_file = "mynewfile.txt"
    with open(os.path.join(worktree.directory, new_file), "w") as file:
        file.writelines(["this is a new file\n"])

    # Remove a file
    file_to_remove = "pyproject.toml"
    os.remove(os.path.join(worktree.directory, file_to_remove))

    git_repo.index.add([new_file])
    git_repo.index.remove([file_to_remove])

    git_repo.index.commit("Add 1, remove 1")

    # TODO Need to move this code, it's useful to modify a file in the repo
    # for branch in ["branch01", "branch02"]:

    #     worktree = repo.get_worktree(identifier=branch)
    #     git_repo = repo.get_git_repo_worktree(identifier=branch)

    #     sports_file = os.path.join(worktree.directory, "test_files/sports.yml")

    #     with open(sports_file, 'r') as file:
    #         data = file.readlines()

    #     # now change the 2nd line, note that you have to add a newline
    #     data[1] = f'sports_{branch}:\n'

    #     # and write everything back
    #     with open(sports_file, 'w') as file:
    #         file.writelines( data )

    #     git_repo.index.add([sports_file])
    #     git_repo.index.commit("Change sport file")

    # repo.merge(source_branch="branch01", dest_branch="main", push_remote=False)

    # commit_main = repo.get_commit_value(branch_name="main", remote=False)

    commit_branch01 = repo.get_commit_value(branch_name=branch01.name, remote=False)
    commit_branch02 = repo.get_commit_value(branch_name=branch02.name, remote=False)

    changed, added, removed = await repo.calculate_diff_between_commits(
        first_commit=commit_branch01, second_commit=commit_branch02
    )
    assert changed == ["README.md", "test_files/sports.yml"]
    assert added == ["mynewfile.txt"]
    assert removed == ["pyproject.toml"]


def test_extract_repo_file_information():
    file_info = extract_repo_file_information(
        full_filename="/tmp/dir1/dir2/dir3/myfile.py", repo_directory="/tmp", worktree_directory="/tmp/dir1"
    )

    assert isinstance(file_info, RepoFileInformation)
    assert file_info.filename == "myfile.py"
    assert file_info.extension == ".py"
    assert file_info.filename_wo_ext == "myfile"
    assert file_info.relative_path_dir == "dir2/dir3"
    assert file_info.relative_repo_path_dir == "dir1/dir2/dir3"
    assert file_info.absolute_path_dir == "/tmp/dir1/dir2/dir3"
    assert file_info.relative_path_file == "dir2/dir3/myfile.py"
    assert file_info.module_name == "dir1.dir2.dir3.myfile"

    file_info = extract_repo_file_information(full_filename="/tmp/dir1/dir2/dir3/myfile.py", repo_directory="/tmp/dir1")

    assert isinstance(file_info, RepoFileInformation)
    assert file_info.filename == "myfile.py"
    assert file_info.extension == ".py"
    assert file_info.filename_wo_ext == "myfile"
    assert file_info.relative_repo_path_dir == "dir2/dir3"
    assert file_info.relative_path_dir == "/tmp/dir1/dir2/dir3"
    assert file_info.absolute_path_dir == "/tmp/dir1/dir2/dir3"
    assert file_info.relative_path_file == "/tmp/dir1/dir2/dir3/myfile.py"
    assert file_info.module_name == "dir2.dir3.myfile"


async def test_create_python_check_definition(
    helper, git_repo_03_w_client: InfrahubRepository, mock_schema_query_01, gql_query_data_01, mock_check_create
):
    repo = git_repo_03_w_client

    module = helper.import_module_in_fixtures(module="checks/check01")
    check_class = getattr(module, "Check01")

    gql_schema = await repo.client.schema.get(kind="CoreGraphQLQuery")

    query = InfrahubNode(client=repo.client, schema=gql_schema, data=gql_query_data_01)

    check = CheckDefinitionInformation(
        name=check_class.__name__,
        class_name=check_class.__name__,
        check_class=check_class,
        repository=str(repo.id),
        file_path="checks/check01/check.py",
        query=str(query.id),
        timeout=check_class.timeout,
        rebase=check_class.rebase,
    )
    obj = await repo.create_python_check_definition(branch_name="main", check=check)

    assert isinstance(obj, InfrahubNode)


async def test_compare_python_check(
    helper,
    git_repo_03_w_client: InfrahubRepository,
    mock_schema_query_01,
    gql_query_data_01,
    gql_query_data_02,
    check_definition_data_01,
):
    repo = git_repo_03_w_client

    module = helper.import_module_in_fixtures(module="checks/check01")
    check_class = getattr(module, "Check01")

    gql_schema = await repo.client.schema.get(kind="CoreGraphQLQuery")
    check_schema = await repo.client.schema.get(kind="CoreCheckDefinition")

    query_01 = InfrahubNode(client=repo.client, schema=gql_schema, data=gql_query_data_01)
    query_02 = InfrahubNode(client=repo.client, schema=gql_schema, data=gql_query_data_02)
    existing_check = InfrahubNode(client=repo.client, schema=check_schema, data=check_definition_data_01)

    check01 = CheckDefinitionInformation(
        name=check_class.__name__,
        class_name=check_class.__name__,
        check_class=check_class,
        repository=str(repo.id),
        file_path="checks/check01/check.py",
        query=str(query_01.id),
        timeout=check_class.timeout,
        rebase=check_class.rebase,
    )

    assert await repo.compare_python_check_definition(existing_check=existing_check, check=check01) is True

    check02 = CheckDefinitionInformation(
        name=check_class.__name__,
        class_name=check_class.__name__,
        check_class=check_class,
        repository=str(repo.id),
        file_path="checks/check01/newpath.py",
        query=str(query_01.id),
        timeout=check_class.timeout,
        rebase=check_class.rebase,
    )

    assert (
        await repo.compare_python_check_definition(
            existing_check=existing_check,
            check=check02,
        )
        is False
    )

    check03 = CheckDefinitionInformation(
        name=check_class.__name__,
        class_name=check_class.__name__,
        check_class=check_class,
        repository=str(repo.id),
        file_path="checks/check01/check.py",
        query=str(query_02.id),
        timeout=check_class.timeout,
        rebase=check_class.rebase,
    )

    assert await repo.compare_python_check_definition(check=check03, existing_check=existing_check) is False
