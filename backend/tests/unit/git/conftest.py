import os
import re
import shutil
import tarfile
import uuid
from pathlib import Path
from typing import Dict

import pytest
import ujson
from git import Repo
from pytest_httpx import HTTPXMock

import infrahub.config as config
from infrahub.git import InfrahubRepository
from infrahub.utils import find_first_file_in_directory, get_fixtures_dir
from infrahub_client import InfrahubClient


@pytest.fixture
async def client() -> InfrahubClient:
    return await InfrahubClient.init(address="http://mock", insert_tracker=True)


@pytest.fixture
def git_sources_dir(tmp_path) -> str:
    source_dir = os.path.join(str(tmp_path), "sources")

    os.mkdir(source_dir)

    return source_dir


@pytest.fixture
def git_repos_dir(tmp_path) -> str:
    repos_dir = os.path.join(str(tmp_path), "repositories")

    os.mkdir(repos_dir)

    config.SETTINGS.git.repositories_directory = repos_dir

    return repos_dir


@pytest.fixture
def git_upstream_repo_01(git_sources_dir) -> Dict[str, str]:
    """Git Repository with 4 branches main, branch01, branch02, and clean-branch.
    There is conflict between branch01 and branch02."""

    name = "infrahub-test-fixture-01"
    here = os.path.abspath(os.path.dirname(__file__))
    fixtures_dir = os.path.join(here, "..", "..", "fixtures")
    fixture_repo = os.path.join(fixtures_dir, "infrahub-test-fixture-01-0b341c0.tar.gz")

    # Extract the fixture package in the source directory
    file = tarfile.open(fixture_repo)
    file.extractall(git_sources_dir)
    file.close()

    return dict(name=name, path=str(os.path.join(git_sources_dir, name)))


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
def git_upstream_repo_10(helper, git_sources_dir) -> Dict[str, str]:
    """Git Repository used as part of the  demo-edge tutorial."""

    name = "infrahub-demo-edge-develop"
    fixtures_dir = helper.get_fixtures_dir()
    fixture_repo = os.path.join(fixtures_dir, "infrahub-demo-edge-8d18455.tar.gz")

    # Extract the fixture package in the source directory
    file = tarfile.open(fixture_repo)
    file.extractall(git_sources_dir)
    file.close()

    return dict(name=name, path=str(os.path.join(git_sources_dir, name)))


@pytest.fixture
async def git_repo_01(client, git_upstream_repo_01, git_repos_dir) -> InfrahubRepository:
    """Git Repository with git_upstream_repo_01 as remote"""

    repo = await InfrahubRepository.new(
        id=uuid.uuid4(),
        name=git_upstream_repo_01["name"],
        location=git_upstream_repo_01["path"],
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
        location=git_upstream_repo_02["path"],
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
        id=uuid.uuid4(), name=git_upstream_repo_03["name"], location=git_upstream_repo_03["path"]
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
        location=git_upstream_repo_03["path"],
    )
    await repo.create_branch_in_git(branch_name="branch01")

    # Checkout branch01 in the upstream repo after the repo has been cloned
    # Update the first file at the top level and commit the change in the branch
    upstream = Repo(git_upstream_repo_03["path"])
    upstream.git.checkout("branch01")

    first_file = find_first_file_in_directory(git_upstream_repo_03["path"])
    with open(os.path.join(git_upstream_repo_03["path"], first_file), "a") as file:
        file.write("new line\n")
    upstream.index.add([first_file])
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
        location=git_upstream_repo_01["path"],
    )

    # Update the first file at the top level and commit the change in the branch
    upstream = Repo(git_upstream_repo_01["path"])
    first_file = find_first_file_in_directory(git_upstream_repo_01["path"])
    with open(os.path.join(git_upstream_repo_01["path"], first_file), "a") as file:
        file.write("new line\n")
    upstream.index.add([first_file])
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
        location=git_upstream_repo_01["path"],
    )
    await repo.create_branch_in_git(branch_name="branch01")

    # Checkout branch01 in the upstream repo after the repo has been cloned
    # Update the first file at the top level and commit the change in the branch
    upstream = Repo(git_upstream_repo_01["path"])
    upstream.git.checkout("branch01")

    first_file = find_first_file_in_directory(git_upstream_repo_01["path"])
    with open(os.path.join(git_upstream_repo_01["path"], first_file), "a") as file:
        file.write("new line\n")
    upstream.index.add([first_file])
    upstream.index.commit("Change first file")

    upstream.git.checkout("main")

    # Update the local branch branch01 to create a conflict.
    branch_wt = repo.get_worktree(identifier="branch01")
    branch_repo = Repo(branch_wt.directory)
    first_file_in_repo = os.path.join(branch_wt.directory, first_file)
    with open(first_file_in_repo, "a") as file:
        file.write("not the same line\n")
    branch_repo.index.add([first_file])
    branch_repo.index.commit("Change first file in main")

    await repo.fetch()

    return repo


@pytest.fixture
async def git_repo_jinja(client, git_upstream_repo_02, git_repos_dir) -> InfrahubRepository:
    """Git Repository with git_upstream_repo_02 as remote
    The repo has 2 local branches : main and branch01
    The main branch contains 2 jinja templates, 1 valid and 1 not valid.
    The content of the first (valid) template, has been modified in the branch branch01

    TODO At some point if would be good to include all these changes in the base repository
    """

    upstream = Repo(git_upstream_repo_02["path"])

    files_to_add = [
        {
            "name": "template01.tpl.j2",
            "content": """
{% for item in items %}
{{ item }}
{% endfor %}
""",
        },
        {
            "name": "template02.tpl.j2",
            "content": """
{% for item in items %}
{{ item }}
{% end %}
""",
        },
    ]

    for file_to_add in files_to_add:
        file_path = os.path.join(git_upstream_repo_02["path"], file_to_add["name"])
        with open(file_path, "w") as file:
            file.write(file_to_add["content"])

        upstream.index.add(file_to_add["name"])
    upstream.index.commit("Add 2 Jinja templates")

    # Create a new branch branch01
    #  Update the first jinja template in the branch
    upstream.git.branch("branch01")
    upstream.git.checkout("branch01")

    file_to_add = files_to_add[0]
    file_path = os.path.join(git_upstream_repo_02["path"], file_to_add["name"])
    new_content = """
{% for item in items %}
 - {{ item }} -
{% endfor %}
"""
    with open(file_path, "w") as file:
        file.write(new_content)
    upstream.index.add(file_to_add["name"])
    upstream.index.commit("Update the first jinja template in the branch")
    upstream.git.checkout("main")

    # Clone the repo and create a local branch for branch01
    repo = await InfrahubRepository.new(
        id=uuid.uuid4(),
        name=git_upstream_repo_02["name"],
        location=git_upstream_repo_02["path"],
    )
    await repo.create_branch_in_git(branch_name="branch01")

    return repo


@pytest.fixture
async def git_repo_checks(client, git_upstream_repo_02, git_repos_dir) -> InfrahubRepository:
    """Git Repository with git_upstream_repo_02 as remote
    The repo has 1 local branch : main
    The main branch contains 2 checks: check01 and check02.
    Check01 always return False and check02 is not valid.
    """

    checks_fixture_dir = os.path.join(get_fixtures_dir(), "checks")
    upstream = Repo(git_upstream_repo_02["path"])

    files_to_copy = ["check01.py", "check02.py"]

    for file_to_copy in files_to_copy:
        shutil.copyfile(
            os.path.join(checks_fixture_dir, file_to_copy), os.path.join(git_upstream_repo_02["path"], file_to_copy)
        )
        upstream.index.add(file_to_copy)

    upstream.index.commit("Add 2 checks files")

    repo = await InfrahubRepository.new(
        id=uuid.uuid4(),
        name=git_upstream_repo_02["name"],
        location=git_upstream_repo_02["path"],
    )
    return repo


@pytest.fixture
async def git_repo_transforms(client, git_upstream_repo_02, git_repos_dir) -> InfrahubRepository:
    """Git Repository with git_upstream_repo_02 as remote
    The repo has 1 local branch : main
    The main branch contains 2 transforms: transform01 and transform02.
    Transform01 will change to uppercase the keys in the data dict always and Transform02 is not valid.
    """

    checks_fixture_dir = os.path.join(get_fixtures_dir(), "transforms")
    upstream = Repo(git_upstream_repo_02["path"])

    files_to_copy = ["transform01.py", "transform02.py"]

    for file_to_copy in files_to_copy:
        shutil.copyfile(
            os.path.join(checks_fixture_dir, file_to_copy), os.path.join(git_upstream_repo_02["path"], file_to_copy)
        )
        upstream.index.add(file_to_copy)

    upstream.index.commit("Add 2 Transforms files")

    repo = await InfrahubRepository.new(
        id=uuid.uuid4(),
        name=git_upstream_repo_02["name"],
        location=git_upstream_repo_02["path"],
    )
    return repo


@pytest.fixture
async def git_repo_10(client, git_upstream_repo_10, git_repos_dir) -> InfrahubRepository:
    """Git Repository with git_upstream_repo_10 as remote"""

    repo = await InfrahubRepository.new(
        id=uuid.uuid4(),
        name=git_upstream_repo_10["name"],
        location=git_upstream_repo_10["path"],
    )

    repo.client = client

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
                    "is_default": True,
                    "origin_branch": None,
                    "branched_from": "2023-02-17T09:30:17.811719Z",
                },
                {
                    "id": "7d9f817a-b958-4e76-8528-8afd0c689ada",
                    "name": "cr1234",
                    "is_data_only": True,
                    "is_default": False,
                    "origin_branch": "main",
                    "branched_from": "2023-02-17T09:30:17.811719Z",
                },
            ]
        }
    }

    httpx_mock.add_response(method="POST", json=response, match_headers={"X-Infrahub-Tracker": "query-branch-all"})
    return httpx_mock


@pytest.fixture
async def mock_repositories_query(httpx_mock: HTTPXMock) -> HTTPXMock:
    response1 = {
        "data": {
            "CoreRepository": {
                "edges": [
                    {
                        "node": {
                            "id": "9486cfce-87db-479d-ad73-07d80ba96a0f",
                            "name": {"value": "infrahub-test-fixture-01"},
                            "location": {"value": "git@github.com:mock/infrahub-test-fixture-01.git"},
                            "commit": {"value": "aaaaaaaaaaaaaaaaaaaa"},
                        }
                    }
                ]
            }
        }
    }
    response2 = {
        "data": {
            "CoreRepository": {
                "edges": [
                    {
                        "node": {
                            "id": "9486cfce-87db-479d-ad73-07d80ba96a0f",
                            "name": {"value": "infrahub-test-fixture-01"},
                            "location": {"value": "git@github.com:mock/infrahub-test-fixture-01.git"},
                            "commit": {"value": "bbbbbbbbbbbbbbbbbbbb"},
                        }
                    }
                ]
            }
        }
    }

    httpx_mock.add_response(method="POST", url="http://mock/graphql/main", json=response1)
    httpx_mock.add_response(method="POST", url="http://mock/graphql/cr1234", json=response2)
    return httpx_mock


@pytest.fixture
async def mock_add_branch01_query(httpx_mock: HTTPXMock) -> HTTPXMock:
    response = {
        "data": {
            "branch_create": {
                "ok": True,
                "object": {
                    "id": "8927425e-fd89-482a-bcec-aad267eb2c66",
                    "name": "branch01",
                    "is_default": False,
                    "is_data_only": False,
                    "description": "",
                    "branched_from": "2023-02-17T09:30:17.811719Z",
                },
            }
        }
    }

    httpx_mock.add_response(
        method="POST", json=response, match_headers={"X-Infrahub-Tracker": "mutation-branch-create"}
    )
    return httpx_mock


@pytest.fixture
async def mock_update_commit_query(httpx_mock: HTTPXMock) -> HTTPXMock:
    response = {
        "data": {
            "branch_create": {"ok": True, "object": {"id": "8927425e-fd89-482a-bcec-aad267eb2c66", "name": "branch01"}}
        }
    }

    httpx_mock.add_response(
        method="POST", json=response, match_headers={"X-Infrahub-Tracker": "mutation-branch-create"}
    )
    return httpx_mock


@pytest.fixture
async def mock_gql_query_my_query(httpx_mock: HTTPXMock) -> HTTPXMock:
    response = {"data": {"mock": []}}

    httpx_mock.add_response(method="GET", json=response, url="http://mock/query/my_query?branch=main&rebase=true")
    return httpx_mock


@pytest.fixture
async def gql_query_data_01() -> dict:
    data = {
        "node": {
            "id": "rrrrrrrr-rrrr-rrrr-rrrr-rrrrrrrrrrrr",
            "display_label": "MyQuery",
            "name": {"is_protected": False, "is_visible": True, "owner": None, "source": None, "value": "MyQuery"},
            "description": {"is_protected": False, "is_visible": True, "owner": None, "source": None, "value": None},
            "query": {
                "is_protected": False,
                "is_visible": True,
                "owner": None,
                "source": None,
                "value": "query MyQuery { location { edges { node { name { value }}}}}",
            },
        }
    }
    return data


@pytest.fixture
async def gql_query_data_02() -> dict:
    data = {
        "node": {
            "id": "mmmmmmmm-nnnn-bbbb-vvvv-cccccccccccc",
            "display_label": "MyOtherQuery",
            "name": {"is_protected": False, "is_visible": True, "owner": None, "source": None, "value": "MyQuery"},
            "description": {"is_protected": False, "is_visible": True, "owner": None, "source": None, "value": None},
            "query": {
                "is_protected": False,
                "is_visible": True,
                "owner": None,
                "source": None,
                "value": "query MyOtherQuery { location { edges { node { name { value }}}}}",
            },
        }
    }
    return data


@pytest.fixture
async def mock_schema_query_01(helper, httpx_mock: HTTPXMock) -> HTTPXMock:
    response_text = Path(os.path.join(helper.get_fixtures_dir(), "schemas", "schema_01.json")).read_text(
        encoding="UTF-8"
    )

    httpx_mock.add_response(method="GET", url="http://mock/schema/?branch=main", json=ujson.loads(response_text))
    return httpx_mock


@pytest.fixture
async def mock_check_create(helper, httpx_mock: HTTPXMock) -> HTTPXMock:
    response = {
        "data": {
            "CoreCheckCreate": {
                "ok": True,
                "object": {
                    "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                },
            }
        }
    }

    httpx_mock.add_response(method="POST", url=re.compile(r"http(.*){3}mock\/graphql\/.*"), json=response)
    return httpx_mock


@pytest.fixture
async def check_data_01() -> dict:
    data = {
        "node": {
            "id": "d32f30f8-1d1e-4dfb-96d9-91234a9ffbe1",
            "display_label": "Check01",
            "name": {
                "value": "Check01",
                "is_protected": True,
                "is_visible": True,
                "source": {
                    "id": "0b843de7-9a5e-4330-acee-9991c359f40a",
                    "display_label": "infrahub-demo-edge",
                    "__typename": "Repository",
                },
                "owner": None,
            },
            "description": {
                "value": None,
                "is_protected": False,
                "is_visible": True,
                "source": None,
                "owner": None,
            },
            "file_path": {
                "value": "checks/check01/check.py",
                "is_protected": True,
                "is_visible": True,
                "source": {
                    "id": "0b843de7-9a5e-4330-acee-9991c359f40a",
                    "display_label": "infrahub-demo-edge",
                    "__typename": "Repository",
                },
                "owner": None,
            },
            "class_name": {
                "value": "Check01",
                "is_protected": True,
                "is_visible": True,
                "source": {
                    "id": "0b843de7-9a5e-4330-acee-9991c359f40a",
                    "display_label": "infrahub-demo-edge",
                    "__typename": "Repository",
                },
                "owner": None,
            },
            "timeout": {
                "value": 10,
                "is_protected": True,
                "is_visible": True,
                "source": {
                    "id": "0b843de7-9a5e-4330-acee-9991c359f40a",
                    "display_label": "infrahub-demo-edge",
                    "__typename": "Repository",
                },
                "owner": None,
            },
            "rebase": {
                "value": True,
                "is_protected": True,
                "is_visible": True,
                "source": {
                    "id": "0b843de7-9a5e-4330-acee-9991c359f40a",
                    "display_label": "infrahub-demo-edge",
                    "__typename": "Repository",
                },
                "owner": None,
            },
            "repository": {
                "node": {
                    "id": "0b843de7-9a5e-4330-acee-9991c359f40a",
                    "display_label": "infrahub-demo-edge",
                    "__typename": "Repository",
                },
                "properties": {
                    "is_protected": True,
                    "is_visible": True,
                    "source": {
                        "id": "0b843de7-9a5e-4330-acee-9991c359f40a",
                        "display_label": "infrahub-demo-edge",
                        "__typename": "Repository",
                    },
                    "owner": None,
                },
            },
            "query": {
                "node": {
                    "id": "rrrrrrrr-rrrr-rrrr-rrrr-rrrrrrrrrrrr",
                    "display_label": "check_backbone_link_redundancy",
                    "__typename": "GraphQLQuery",
                },
                "properties": {
                    "is_protected": True,
                    "is_visible": True,
                    "source": {
                        "id": "0b843de7-9a5e-4330-acee-9991c359f40a",
                        "display_label": "infrahub-demo-edge",
                        "__typename": "Repository",
                    },
                    "owner": None,
                },
            },
            "tags": {"edges": []},
            "__typename": "Check",
        },
    }

    return data
