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

from infrahub.git import InfrahubRepository, QUERY_BRANCHES, QUERY_REPOSITORY, MUTATION_BRANCH_CREATE
from infrahub.message_bus.events import (
    InfrahubGitRPC,
    GitMessageAction,
)
from infrahub_client import MUTATION_BRANCH_CREATE


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
    """Git Repository with  as remote"""

    repo = await InfrahubRepository.new(
        id=uuid.uuid4(),
        name=git_upstream_repo_01["name"],
        location=f"file:/{git_upstream_repo_01['path']}",
    )

    return repo


@pytest.fixture
async def git_repo_01_w_client(git_repo_01, client) -> InfrahubRepository:
    """Git Repository with  as remote"""

    git_repo_01.client = client
    return git_repo_01


@pytest.fixture
async def git_repo_02(git_upstream_repo_02, git_repos_dir) -> InfrahubRepository:

    repo = await InfrahubRepository.new(
        id=uuid.uuid4(),
        name=git_upstream_repo_02["name"],
        location=f"file:/{git_upstream_repo_02['path']}",
    )

    return repo


@pytest.fixture
async def git_repo_02_w_client(git_repo_02, client) -> InfrahubRepository:
    """Git Repository with  as remote"""

    git_repo_02.client = client
    return git_repo_02


@pytest.fixture
async def git_repo_03(client, git_upstream_repo_03, git_repos_dir) -> InfrahubRepository:

    repo = await InfrahubRepository.new(
        id=uuid.uuid4(), name=git_upstream_repo_03["name"], location=f"file:/{git_upstream_repo_03['path']}"
    )

    return repo


@pytest.fixture
async def git_repo_03_w_client(git_repo_03, client) -> InfrahubRepository:
    """Git Repository with  as remote"""

    git_repo_03.client = client
    return git_repo_03


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
    request_content = json.dumps({"query": QUERY_BRANCHES}).encode()

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
