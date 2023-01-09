import os
import tarfile

from typing import Dict
import json
import uuid
import pytest

from git import Repo

from pytest_httpx import HTTPXMock
import infrahub.config as config

from infrahub_client import InfrahubClient

from infrahub.git import InfrahubRepository
from infrahub.message_bus.events import (
    InfrahubGitRPC,
    GitMessageAction,
)
from infrahub_client import MUTATION_BRANCH_CREATE, QUERY_ALL_BRANCHES


@pytest.fixture
async def client() -> InfrahubClient:

    return await InfrahubClient.init(address="http://mock")


@pytest.fixture
def git_sources_dir(tmpdir) -> str:

    source_dir = os.path.join(str(tmpdir), "sources")

    os.mkdir(source_dir)

    return source_dir


@pytest.fixture
def git_repos_dir(tmpdir) -> str:

    repos_dir = os.path.join(str(tmpdir), "repositories")

    os.mkdir(repos_dir)

    config.SETTINGS.main.repositories_directory = repos_dir

    return repos_dir


@pytest.fixture
def git_upstream_repo_01(git_sources_dir) -> Dict[str, str]:
    """Git Repository with 4 branches main, branch01, branch02, and clean-branch.
    There is conflict between branch01 and branch02."""

    name = "infrahub-test-fixture-01"
    fixtures_dir = os.path.join(os.getcwd(), "tests/fixtures")
    fixture_repo = os.path.join(fixtures_dir, "infrahub-test-fixture-01-0b341c0.tar.gz")

    # Extract the fixture package in the source directory
    file = tarfile.open(fixture_repo)
    file.extractall(git_sources_dir)
    file.close()

    return dict(name=name, path=os.path.join(git_sources_dir, "infrahub-test-fixture-01"))


@pytest.fixture
def git_upstream_repo_02(git_upstream_repo_01) -> Dict[str, str]:
    """Delete all the branches but the main branch from git_upstream_repo_01"""
    repo = Repo(git_upstream_repo_01["path"])

    for local_branch in repo.refs:
        if local_branch.is_remote() or str(local_branch) == "main":
            continue

        repo.git.branch("-D", str(local_branch))

    return git_upstream_repo_01


@pytest.fixture
def git_upstream_repo_03(git_upstream_repo_01) -> Dict[str, str]:
    """Delete all the branches but the main branch and the branch branch01 from git_upstream_repo_01"""
    repo = Repo(git_upstream_repo_01["path"])

    for local_branch in repo.refs:
        if local_branch.is_remote() or str(local_branch) in ["main", "branch01"]:
            continue

        repo.git.branch("-D", str(local_branch))

    return git_upstream_repo_01


@pytest.fixture
async def git_repo_01(client, git_upstream_repo_01, git_repos_dir) -> InfrahubRepository:
    """Git Repository with git_upstream_repo_01 as remote"""

    repo = await InfrahubRepository.new(
        id=uuid.uuid4(),
        name=git_upstream_repo_01["name"],
        location=f"file:/{git_upstream_repo_01['path']}",
    )

    return repo


@pytest.fixture
async def git_repo_01_w_client(git_repo_01, client) -> InfrahubRepository:
    """Same as fixture git_repo_01 but with a Infrahub client initialized."""

    git_repo_01.client = client
    return git_repo_01


@pytest.fixture
async def git_repo_02(git_upstream_repo_02, git_repos_dir) -> InfrahubRepository:
    """Git Repository with git_upstream_repo_02 as remote"""
    repo = await InfrahubRepository.new(
        id=uuid.uuid4(),
        name=git_upstream_repo_02["name"],
        location=f"file:/{git_upstream_repo_02['path']}",
    )

    return repo


@pytest.fixture
async def git_repo_02_w_client(git_repo_02, client) -> InfrahubRepository:
    """Same as fixture git_repo_02 but with a Infrahub client initialized."""

    git_repo_02.client = client
    return git_repo_02


@pytest.fixture
async def git_repo_03(client, git_upstream_repo_03, git_repos_dir) -> InfrahubRepository:
    """Git Repository with git_upstream_repo_03 as remote"""
    repo = await InfrahubRepository.new(
        id=uuid.uuid4(), name=git_upstream_repo_03["name"], location=f"file:/{git_upstream_repo_03['path']}"
    )

    return repo


@pytest.fixture
async def git_repo_03_w_client(git_repo_03, client) -> InfrahubRepository:
    """Same as fixture git_repo_03 but with a Infrahub client initialized."""

    git_repo_03.client = client
    return git_repo_03


@pytest.fixture
async def git_repo_04(client, git_upstream_repo_03, git_repos_dir) -> InfrahubRepository:
    """Git Repository with git_upstream_repo_01 as remote
    The repo has 2 local branches : main and branch01
    The content of the branch branch01 has been  updated after the repo has been initialized
    to generate a diff between the local and the remote branch branch01.
    """

    repo = await InfrahubRepository.new(
        id=uuid.uuid4(),
        name=git_upstream_repo_03["name"],
        location=f"file:/{git_upstream_repo_03['path']}",
    )
    await repo.create_branch_in_git(branch_name="branch01")

    # Checkout branch01 in the upstream repo after the repo has been cloned
    # Update the first file at the top level and commit the change in the branch
    upstream = Repo(git_upstream_repo_03["path"])
    upstream.git.checkout("branch01")

    top_level_files = os.listdir(git_upstream_repo_03["path"])
    first_file = os.path.join(git_upstream_repo_03["path"], top_level_files[0])
    with open(first_file, "a") as file:
        file.write("new line\n")
    upstream.index.add([top_level_files[0]])
    upstream.index.commit("Change first file")

    upstream.git.checkout("main")

    await repo.fetch()

    return repo


@pytest.fixture
async def git_repo_05(client, git_upstream_repo_01, git_repos_dir) -> InfrahubRepository:
    """Git Repository with git_upstream_repo_01 as remote
    The repo has 1 local : main
    The content of the main branch has been  updated after the repo has been initialized
    to generate a diff between the local and the remote branch main.
    """

    repo = await InfrahubRepository.new(
        id=uuid.uuid4(),
        name=git_upstream_repo_01["name"],
        location=f"file:/{git_upstream_repo_01['path']}",
    )

    # Update the first file at the top level and commit the change in the branch
    upstream = Repo(git_upstream_repo_01["path"])
    top_level_files = os.listdir(git_upstream_repo_01["path"])
    first_file = os.path.join(git_upstream_repo_01["path"], top_level_files[0])
    with open(first_file, "a") as file:
        file.write("new line\n")
    upstream.index.add([top_level_files[0]])
    upstream.index.commit("Change first file")

    await repo.fetch()

    return repo


@pytest.fixture
async def git_repo_06(client, git_upstream_repo_01, git_repos_dir) -> InfrahubRepository:
    """Git Repository with git_upstream_repo_01 as remote
    The repo has 2 local branches : main and branch01
    The content of the branch branch01 has been  updated both locally and in the remote after the repo has been initialized
    to generate a conflict between the local and the remote branch branch01.
    """

    repo = await InfrahubRepository.new(
        id=uuid.uuid4(),
        name=git_upstream_repo_01["name"],
        location=f"file:/{git_upstream_repo_01['path']}",
    )
    await repo.create_branch_in_git(branch_name="branch01")

    # Checkout branch01 in the upstream repo after the repo has been cloned
    # Update the first file at the top level and commit the change in the branch
    upstream = Repo(git_upstream_repo_01["path"])
    upstream.git.checkout("branch01")

    top_level_files = os.listdir(git_upstream_repo_01["path"])
    first_file = os.path.join(git_upstream_repo_01["path"], top_level_files[0])
    with open(first_file, "a") as file:
        file.write("new line\n")
    upstream.index.add([top_level_files[0]])
    upstream.index.commit("Change first file")

    upstream.git.checkout("main")

    # Update the local branch branch01 to create a conflict.
    branch_wt = repo.get_worktree(identifier="branch01")
    branch_repo = Repo(branch_wt.directory)
    first_file_in_repo = os.path.join(branch_wt.directory, top_level_files[0])

    with open(first_file_in_repo, "a") as file:
        file.write("not the same line\n")
    branch_repo.index.add([top_level_files[0]])
    branch_repo.index.commit("Change first file in main")

    await repo.fetch()

    return repo


@pytest.fixture
async def mock_branches_list_query(httpx_mock: HTTPXMock) -> HTTPXMock:

    response = {
        "data": {
            "branch": [
                {
                    "id": "eca306cf-662e-4e03-8180-2b788b191d3c",
                    "name": "main",
                    "is_data_only": False,
                },
                {
                    "id": "7d9f817a-b958-4e76-8528-8afd0c689ada",
                    "name": "cr1234",
                    "is_data_only": True,
                },
            ]
        }
    }
    request_content = json.dumps({"query": QUERY_ALL_BRANCHES}).encode()

    httpx_mock.add_response(method="POST", json=response, match_content=request_content)
    return httpx_mock


@pytest.fixture
async def mock_repositories_query(httpx_mock: HTTPXMock) -> HTTPXMock:

    response1 = {
        "data": {
            "repository": [
                {
                    "id": "9486cfce-87db-479d-ad73-07d80ba96a0f",
                    "name": {"value": "infrahub-test-fixture-01"},
                    "location": {"value": "git@github.com:mock/infrahub-test-fixture-01.git"},
                    "commit": {"value": "aaaaaaaaaaaaaaaaaaaa"},
                }
            ]
        }
    }
    response2 = {
        "data": {
            "repository": [
                {
                    "id": "9486cfce-87db-479d-ad73-07d80ba96a0f",
                    "name": {"value": "infrahub-test-fixture-01"},
                    "location": {"value": "git@github.com:mock/infrahub-test-fixture-01.git"},
                    "commit": {"value": "bbbbbbbbbbbbbbbbbbbb"},
                }
            ]
        }
    }

    httpx_mock.add_response(method="POST", url="http://mock/graphql/main", json=response1)
    httpx_mock.add_response(method="POST", url="http://mock/graphql/cr1234", json=response2)
    return httpx_mock


@pytest.fixture
async def mock_add_branch01_query(httpx_mock: HTTPXMock) -> HTTPXMock:

    response = {
        "data": {
            "branch_create": {"ok": True, "object": {"id": "8927425e-fd89-482a-bcec-aad267eb2c66", "name": "branch01"}}
        }
    }
    request_content = json.dumps(
        {"query": MUTATION_BRANCH_CREATE, "variables": {"branch_name": "branch01", "background_execution": True}}
    ).encode()

    httpx_mock.add_response(method="POST", json=response, match_content=request_content)
    return httpx_mock


@pytest.fixture
async def mock_update_commit_query(httpx_mock: HTTPXMock) -> HTTPXMock:

    response = {
        "data": {
            "branch_create": {"ok": True, "object": {"id": "8927425e-fd89-482a-bcec-aad267eb2c66", "name": "branch01"}}
        }
    }
    request_content = json.dumps({"query": MUTATION_BRANCH_CREATE, "variables": {"branch_name": "branch01"}}).encode()

    httpx_mock.add_response(method="POST", json=response, match_content=request_content)
    return httpx_mock


@pytest.fixture
def git_rpc_repo_add_01(git_upstream_repo_01):

    return InfrahubGitRPC(
        action=GitMessageAction.REPO_ADD.value,
        repository_id=uuid.uuid4(),
        repository_name=git_upstream_repo_01["name"],
        location=f"file:/{git_upstream_repo_01['path']}",
    )


@pytest.fixture
def git_rpc_repo_add_02(git_upstream_repo_02):

    return InfrahubGitRPC(
        action=GitMessageAction.REPO_ADD.value,
        repository_id=uuid.uuid4(),
        repository_name=git_upstream_repo_02["name"],
        location=f"file:/{git_upstream_repo_02['path']}",
    )
