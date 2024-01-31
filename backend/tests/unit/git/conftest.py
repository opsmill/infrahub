import os
import re
import shutil
import tarfile
from pathlib import Path
from typing import Dict

import pytest
import ujson
from git import Repo
from infrahub_sdk import UUIDT, InfrahubClient, InfrahubNode
from infrahub_sdk import SchemaRoot as ClientSchemaRoot
from infrahub_sdk.branch import BranchData
from pytest_httpx import HTTPXMock

from infrahub.core.constants import InfrahubKind
from infrahub.core.schema import SchemaRoot, core_models
from infrahub.git import InfrahubRepository
from infrahub.git.repository import InfrahubReadOnlyRepository
from infrahub.utils import find_first_file_in_directory, get_fixtures_dir


@pytest.fixture
async def client() -> InfrahubClient:
    return await InfrahubClient.init(address="http://mock", insert_tracker=True)


@pytest.fixture
def branch01():
    return BranchData(
        id="6c915158-d8ef-4169-9b00-59f94716b8c3 ",
        name="branch01",
        is_data_only=True,
        is_default=False,
        branched_from="main",
    )


@pytest.fixture
def branch02():
    return BranchData(
        id="7708dcea-f7b4-4f5a-b5e9-a0605d4c11ba",
        name="branch02",
        is_data_only=True,
        is_default=False,
        branched_from="main",
    )


@pytest.fixture
def branch99():
    return BranchData(
        id="2e933717-086c-47cf-8242-21421dd3c2bb",
        name="branch99",
        is_data_only=True,
        is_default=False,
        branched_from="main",
    )


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

    name = "infrahub-demo-edge"
    fixtures_dir = helper.get_fixtures_dir()
    fixture_repo = os.path.join(fixtures_dir, "infrahub-demo-edge-cff6665.tar.gz")

    # Extract the fixture package in the source directory
    file = tarfile.open(fixture_repo)
    file.extractall(git_sources_dir)
    file.close()

    return dict(name=name, path=str(os.path.join(git_sources_dir, name)))


@pytest.fixture
async def git_repo_01(client, git_upstream_repo_01, git_repos_dir) -> InfrahubRepository:
    """Git Repository with git_upstream_repo_01 as remote"""

    repo = await InfrahubRepository.new(
        id=UUIDT.new(),
        name=git_upstream_repo_01["name"],
        location=git_upstream_repo_01["path"],
    )

    return repo


@pytest.fixture
async def git_repo_01_read_only(client, git_upstream_repo_01, git_repos_dir) -> InfrahubReadOnlyRepository:
    """Git Repository with git_upstream_repo_01 as remote"""

    repo = await InfrahubReadOnlyRepository.new(
        id=UUIDT.new(),
        name=git_upstream_repo_01["name"],
        location=git_upstream_repo_01["path"],
        ref="branch01",
        infrahub_branch_name="main",
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
        id=UUIDT.new(),
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
        id=UUIDT.new(), name=git_upstream_repo_03["name"], location=git_upstream_repo_03["path"]
    )

    return repo


@pytest.fixture
async def git_repo_03_w_client(git_repo_03, client) -> InfrahubRepository:
    """Same as fixture git_repo_03 but with a Infrahub client initialized."""

    git_repo_03.client = client
    return git_repo_03


@pytest.fixture
async def git_repo_04(client, git_upstream_repo_03, git_repos_dir, branch01: BranchData) -> InfrahubRepository:
    """Git Repository with git_upstream_repo_01 as remote
    The repo has 2 local branches : main and branch01
    The content of the branch branch01 has been  updated after the repo has been initialized
    to generate a diff between the local and the remote branch branch01.
    """

    repo = await InfrahubRepository.new(
        id=UUIDT.new(),
        name=git_upstream_repo_03["name"],
        location=git_upstream_repo_03["path"],
    )
    await repo.create_branch_in_git(branch_name=branch01.name, branch_id=branch01.id)

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
        id=UUIDT.new(),
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
async def git_repo_06(client, git_upstream_repo_01, git_repos_dir, branch01: BranchData) -> InfrahubRepository:
    """Git Repository with git_upstream_repo_01 as remote
    The repo has 2 local branches : main and branch01
    The content of the branch branch01 has been  updated both locally and in the remote after the repo has been initialized
    to generate a conflict between the local and the remote branch branch01.
    """

    repo = await InfrahubRepository.new(
        id=UUIDT.new(),
        name=git_upstream_repo_01["name"],
        location=git_upstream_repo_01["path"],
    )
    await repo.create_branch_in_git(branch_name=branch01.name, branch_id=branch01.id)

    # Checkout branch01 in the upstream repo after the repo has been cloned
    # Update the first file at the top level and commit the change in the branch
    upstream = Repo(git_upstream_repo_01["path"])
    upstream.git.checkout(branch01.name)

    first_file = find_first_file_in_directory(git_upstream_repo_01["path"])
    with open(os.path.join(git_upstream_repo_01["path"], first_file), "a") as file:
        file.write("new line\n")
    upstream.index.add([first_file])
    upstream.index.commit("Change first file")

    upstream.git.checkout("main")

    # Update the local branch branch01 to create a conflict.
    branch_wt = repo.get_worktree(identifier=branch01.name)
    branch_repo = Repo(branch_wt.directory)
    first_file_in_repo = os.path.join(branch_wt.directory, first_file)
    with open(first_file_in_repo, "a") as file:
        file.write("not the same line\n")
    branch_repo.index.add([first_file])
    branch_repo.index.commit("Change first file in main")

    await repo.fetch()

    return repo


@pytest.fixture
async def git_repo_jinja(client, git_upstream_repo_02, git_repos_dir, branch01: BranchData) -> InfrahubRepository:
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
{% for item in data["items"] %}
{{ item }}
{% endfor %}
""",
        },
        {
            "name": "template02.tpl.j2",
            "content": """
{% for item in data["items"] %}
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
    upstream.git.branch(branch01.name)
    upstream.git.checkout(branch01.name)

    file_to_add = files_to_add[0]
    file_path = os.path.join(git_upstream_repo_02["path"], file_to_add["name"])
    new_content = """
{% for item in data["items"] %}
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
        id=UUIDT.new(),
        name=git_upstream_repo_02["name"],
        location=git_upstream_repo_02["path"],
    )
    await repo.create_branch_in_git(branch_name=branch01.name, branch_id=branch01.id)

    return repo


@pytest.fixture
async def git_repo_jinja_w_client(git_repo_jinja, client) -> InfrahubRepository:
    git_repo_jinja.client = client
    return git_repo_jinja


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
        id=UUIDT.new(),
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
        id=UUIDT.new(),
        name=git_upstream_repo_02["name"],
        location=git_upstream_repo_02["path"],
    )
    return repo


@pytest.fixture
async def git_repo_transforms_w_client(git_repo_transforms, client) -> InfrahubRepository:
    git_repo_transforms.client = client
    return git_repo_transforms


@pytest.fixture
async def git_repo_10(client, git_upstream_repo_10, git_repos_dir) -> InfrahubRepository:
    """Git Repository with git_upstream_repo_10 as remote"""

    repo = await InfrahubRepository.new(
        id=UUIDT.new(),
        name=git_upstream_repo_10["name"],
        location=git_upstream_repo_10["path"],
    )

    repo.client = client

    return repo


@pytest.fixture
async def mock_branches_list_query(httpx_mock: HTTPXMock) -> HTTPXMock:
    response = {
        "data": {
            "Branch": [
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
            InfrahubKind.REPOSITORY: {
                "edges": [
                    {
                        "node": {
                            "__typename": "CoreRepository",
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
            InfrahubKind.REPOSITORY: {
                "edges": [
                    {
                        "node": {
                            "__typename": "CoreRepository",
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
            "BranchCreate": {
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
            "BranchCreate": {"ok": True, "object": {"id": "8927425e-fd89-482a-bcec-aad267eb2c66", "name": "branch01"}}
        }
    }

    httpx_mock.add_response(
        method="POST", json=response, match_headers={"X-Infrahub-Tracker": "mutation-branch-create"}
    )
    return httpx_mock


@pytest.fixture
async def mock_gql_query_my_query(httpx_mock: HTTPXMock) -> HTTPXMock:
    response = {"data": {"mock": []}}

    httpx_mock.add_response(
        method="POST", json=response, url="http://mock/api/query/my_query?branch=main&rebase=true&update_group=false"
    )
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

    httpx_mock.add_response(method="GET", url="http://mock/api/schema/?branch=main", json=ujson.loads(response_text))
    return httpx_mock


@pytest.fixture
async def mock_schema_query_02(helper, httpx_mock: HTTPXMock) -> HTTPXMock:
    response_text = Path(os.path.join(helper.get_fixtures_dir(), "schemas", "schema_02.json")).read_text(
        encoding="UTF-8"
    )

    httpx_mock.add_response(method="GET", url="http://mock/api/schema/?branch=main", json=ujson.loads(response_text))
    return httpx_mock


@pytest.fixture
async def mock_check_create(helper, httpx_mock: HTTPXMock) -> HTTPXMock:
    response = {
        "data": {
            InfrahubKind.CHECKDEFINITION: {
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
async def check_definition_data_01() -> dict:
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


@pytest.fixture
async def gql_query_data_03():
    # QUERY
    query_string = """
    query {
        TestPerson {
            edges {
                node {
                    name {
                        value
                    }
                    cars {
                        edges {
                            node {
                                name {
                                    value
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    """

    data = {
        "id": "42665742-002b-4f98-b2e0-1ae716c1efbe",
        "type": InfrahubKind.GRAPHQLQUERY,
        "name": {
            "id": "55d01ee8-d839-4cc4-b312-3fbdd935f40b",
            "__typename": "Text",
            "value": "query01",
            "source": None,
            "owner": None,
            "is_visible": True,
            "is_protected": False,
        },
        "description": {
            "id": "1088765d-92ad-46c3-bfec-bafc74a77682",
            "__typename": "Text",
            "source": None,
            "owner": None,
            "is_visible": True,
            "is_protected": False,
        },
        "query": {
            "id": "226cec9e-2b01-450b-a5cb-ebfa6c87d736",
            "__typename": "TextArea",
            "value": query_string,
            "source": None,
            "owner": None,
            "is_visible": True,
            "is_protected": False,
        },
        "__typename": InfrahubKind.GRAPHQLQUERY,
        "display_label": "query01",
    }
    return data


@pytest.fixture
async def schema_02(client, helper, car_data_01) -> ClientSchemaRoot:
    full_schema = ujson.loads(
        Path(os.path.join(helper.get_fixtures_dir(), "schemas", "schema_02.json")).read_text(encoding="UTF-8")
    )

    return ClientSchemaRoot(**full_schema)


@pytest.fixture
async def gql_query_node_03(client, gql_query_data_03) -> InfrahubNode:
    schema = [model for model in SchemaRoot(**core_models).nodes if model.kind == InfrahubKind.GRAPHQLQUERY][0]
    node = InfrahubNode(client=client, schema=schema, data=gql_query_data_03)
    return node


@pytest.fixture
async def mock_gql_query_03(httpx_mock: HTTPXMock) -> HTTPXMock:
    response = {"data": {"key1": "value1", "key2": "value2"}}
    httpx_mock.add_response(
        method="POST", json=response, match_headers={"X-Infrahub-Tracker": "artifact-query-graphql-data"}
    )
    return httpx_mock


@pytest.fixture
async def mock_gql_query_04(httpx_mock: HTTPXMock) -> HTTPXMock:
    response = {"data": {"items": ["consilium", "potum", "album", "magnum"]}}
    httpx_mock.add_response(
        method="POST", json=response, match_headers={"X-Infrahub-Tracker": "artifact-query-graphql-data"}
    )
    return httpx_mock


@pytest.fixture
async def mock_missing_artifact(httpx_mock: HTTPXMock) -> HTTPXMock:
    response = {"data": {InfrahubKind.ARTIFACT: {"edges": []}}}
    httpx_mock.add_response(
        method="POST", json=response, match_headers={"X-Infrahub-Tracker": "query-coreartifact-page1"}
    )
    return httpx_mock


@pytest.fixture
async def mock_existing_artifact_same(httpx_mock: HTTPXMock) -> HTTPXMock:
    response = {
        "data": {
            InfrahubKind.ARTIFACT: {
                "edges": [
                    {
                        "node": {
                            "id": "0d9a10bd-77f3-4388-a2fb-3cff9586cbb8",
                            "display_label": "openconfig-interfaces",
                            "name": {"value": "openconfig-interfaces", "__typename": "TextAttribute"},
                            "content_type": {"value": "application/json", "__typename": "TextAttribute"},
                            "checksum": {"value": "e889b9fab24aab3b23ea01d5342b514a", "__typename": "TextAttribute"},
                            "storage_id": {
                                "value": "13c8914b-0ac0-4c8c-83ec-a79a1f8ad483",
                                "__typename": "TextAttribute",
                            },
                            "created_at": {"value": None, "__typename": "TextAttribute"},
                            "parameters": {"value": None, "__typename": "JSONAttribute"},
                            "object": {
                                "node": {
                                    "id": "56b6e5a8-2ca2-4b0d-aa07-806fcf8181b0",
                                    "display_label": "ord1-edge1",
                                    "__typename": "InfraDevice",
                                },
                                "__typename": "NestedEdgedCoreNode",
                            },
                            "definition": {
                                "node": {
                                    "id": "683afb8d-b5cf-4585-b864-d1426e13c2dc",
                                    "display_label": "Open Config Interfaces for Edge devices",
                                    "__typename": InfrahubKind.ARTIFACTDEFINITION,
                                },
                                "__typename": f"NestedEdged{InfrahubKind.ARTIFACTDEFINITION}",
                            },
                            "__typename": InfrahubKind.ARTIFACT,
                        },
                    }
                ],
            }
        }
    }
    httpx_mock.add_response(
        method="POST", json=response, match_headers={"X-Infrahub-Tracker": "query-coreartifact-page1"}
    )
    return httpx_mock


@pytest.fixture
async def mock_existing_artifact_different(httpx_mock: HTTPXMock) -> HTTPXMock:
    response = {
        "data": {
            InfrahubKind.ARTIFACT: {
                "edges": [
                    {
                        "node": {
                            "id": "0d9a10bd-77f3-4388-a2fb-3cff9586cbb8",
                            "display_label": "openconfig-interfaces",
                            "name": {"value": "openconfig-interfaces", "__typename": "TextAttribute"},
                            "content_type": {"value": "application/json", "__typename": "TextAttribute"},
                            "checksum": {"value": "aaaa40b1dd39530d1a502e017e0feff5", "__typename": "TextAttribute"},
                            "storage_id": {
                                "value": "13c8914b-0ac0-4c8c-83ec-a79a1f8ad483",
                                "__typename": "TextAttribute",
                            },
                            "created_at": {"value": None, "__typename": "TextAttribute"},
                            "parameters": {"value": None, "__typename": "JSONAttribute"},
                            "object": {
                                "node": {
                                    "id": "56b6e5a8-2ca2-4b0d-aa07-806fcf8181b0",
                                    "display_label": "ord1-edge1",
                                    "__typename": "InfraDevice",
                                },
                                "__typename": "NestedEdgedCoreNode",
                            },
                            "definition": {
                                "node": {
                                    "id": "683afb8d-b5cf-4585-b864-d1426e13c2dc",
                                    "display_label": "Open Config Interfaces for Edge devices",
                                    "__typename": InfrahubKind.ARTIFACTDEFINITION,
                                },
                                "__typename": f"NestedEdged{InfrahubKind.ARTIFACTDEFINITION}",
                            },
                            "__typename": InfrahubKind.ARTIFACT,
                        },
                    }
                ],
            }
        }
    }
    httpx_mock.add_response(
        method="POST", json=response, match_headers={"X-Infrahub-Tracker": "query-coreartifact-page1"}
    )
    return httpx_mock


@pytest.fixture
async def mock_upload_content(httpx_mock: HTTPXMock) -> HTTPXMock:
    response = {"identifier": "ee04f134-a68c-4158-a3c8-3ba5e9cc0c9a", "checksum": "9f60b79b76a902ab130c1313de6a8ac0"}
    httpx_mock.add_response(
        method="POST", json=response, match_headers={"X-Infrahub-Tracker": "artifact-upload-content"}
    )
    return httpx_mock


@pytest.fixture
async def artifact_definition_data_01():
    data = {
        "id": "c4908d78-7b24-45e2-9252-96d0fb3e2c78",
        "type": InfrahubKind.ARTIFACTDEFINITION,
        "name": {
            "id": "8b0423a7-cd5c-4642-b518-db56cc8185c7",
            "__typename": "Text",
            "value": "artifactdef01",
        },
        "artifact_name": {
            "id": "bfca3cdb-d294-4b3a-863a-b74d0a103460",
            "__typename": "Text",
            "value": "myartifact",
        },
        "description": {
            "id": "cb2e8084-8769-4dca-acca-077d15ebb85f",
            "__typename": "Text",
        },
        "parameters": {
            "id": "66e58d66-be81-4ea3-a139-af39a7450055",
            "__typename": "JSON",
            "value": {"name": "name__value"},
        },
        "content_type": {
            "id": "a5acbbb5-c6f7-418e-9f53-c4039d9e5c19",
            "__typename": "Text",
            "value": "application/json",
        },
        "__typename": InfrahubKind.ARTIFACTDEFINITION,
        "display_label": "artifactdef01",
    }
    return data


@pytest.fixture
async def artifact_definition_node_01(client, schema_02: ClientSchemaRoot, artifact_definition_data_01) -> InfrahubNode:
    schema = [model for model in schema_02.nodes if model.kind == InfrahubKind.ARTIFACTDEFINITION][0]
    node = InfrahubNode(client=client, schema=schema, data=artifact_definition_data_01)
    return node


@pytest.fixture
async def artifact_definition_data_02():
    data = {
        "id": "c4908d78-7b24-45e2-9252-96d0fb3e2c78",
        "type": InfrahubKind.ARTIFACTDEFINITION,
        "name": {
            "id": "8b0423a7-cd5c-4642-b518-db56cc8185c7",
            "__typename": "Text",
            "value": "artifactdef02",
        },
        "artifact_name": {
            "id": "bfca3cdb-d294-4b3a-863a-b74d0a103460",
            "__typename": "Text",
            "value": "myartifact",
        },
        "description": {
            "id": "cb2e8084-8769-4dca-acca-077d15ebb85f",
            "__typename": "Text",
        },
        "parameters": {
            "id": "66e58d66-be81-4ea3-a139-af39a7450055",
            "__typename": "JSON",
            "value": {"name": "name__value"},
        },
        "content_type": {
            "id": "a5acbbb5-c6f7-418e-9f53-c4039d9e5c19",
            "__typename": "Text",
            "value": "text/plain",
        },
        "__typename": InfrahubKind.ARTIFACTDEFINITION,
        "display_label": "artifactdef02",
    }
    return data


@pytest.fixture
async def artifact_definition_node_02(client, schema_02: ClientSchemaRoot, artifact_definition_data_02) -> InfrahubNode:
    schema = [model for model in schema_02.nodes if model.kind == InfrahubKind.ARTIFACTDEFINITION][0]
    node = InfrahubNode(client=client, schema=schema, data=artifact_definition_data_02)
    return node


@pytest.fixture
async def artifact_data_01():
    data = {
        "id": "c4908d78-7b24-45e2-9252-96d0fb3e2c78",
        "type": "CoreArtifact",
        "name": {
            "id": "8b0423a7-cd5c-4642-b518-db56cc8185c7",
            "__typename": "Text",
            "value": "artifact01",
        },
        "content_type": {
            "id": "a5acbbb5-c6f7-418e-9f53-c4039d9e5c19",
            "__typename": "Text",
            "value": "text/plain",
        },
        "status": {
            "id": "qwertyui-c6f7-418e-9f53-c4039d9e5c19",
            "__typename": "Text",
            "value": "Pending",
        },
        "__typename": InfrahubKind.ARTIFACT,
        "display_label": "artifact01",
    }
    return data


@pytest.fixture
async def artifact_node_01(client, schema_02: ClientSchemaRoot, artifact_data_01) -> InfrahubNode:
    schema = [model for model in schema_02.nodes if model.kind == InfrahubKind.ARTIFACT][0]
    node = InfrahubNode(client=client, schema=schema, data=artifact_data_01)
    return node


@pytest.fixture
async def artifact_data_02():
    data = {
        "id": "c4908d78-7b24-45e2-9252-96d0fb3e2c78",
        "type": InfrahubKind.ARTIFACT,
        "name": {
            "id": "8b0423a7-cd5c-4642-b518-db56cc8185c7",
            "__typename": "Text",
            "value": "artifact01",
        },
        "content_type": {
            "id": "a5acbbb5-c6f7-418e-9f53-c4039d9e5c19",
            "__typename": "Text",
            "value": "text/plain",
        },
        "status": {
            "id": "qwertyui-c6f7-418e-9f53-c4039d9e5c19",
            "__typename": "Text",
            "value": "Pending",
        },
        "checksum": {"value": "e889b9fab24aab3b23ea01d5342b514a", "__typename": "Text"},
        "storage_id": {"value": "13c8914b-0ac0-4c8c-83ec-a79a1f8ad483", "__typename": "Text"},
        "__typename": InfrahubKind.ARTIFACT,
        "display_label": "artifact01",
    }
    return data


@pytest.fixture
async def artifact_node_02(client, schema_02: ClientSchemaRoot, artifact_data_02) -> InfrahubNode:
    schema = [model for model in schema_02.nodes if model.kind == InfrahubKind.ARTIFACT][0]
    node = InfrahubNode(client=client, schema=schema, data=artifact_data_02)
    return node


@pytest.fixture
async def transformation_data_01() -> dict:
    data = {
        "id": "a0d4c22a-5f60-4bf9-a53f-f9a335420492",
        "type": "CoreTransformPython",
        "file_path": {
            "id": "bad6d5d0-8801-41bc-9c8c-d584b2a47a58",
            "__typename": "Text",
            "value": "transform01.py",
            "source": None,
            "owner": None,
            "is_visible": True,
            "is_protected": False,
        },
        "class_name": {
            "id": "8dc7b35b-c303-4799-9b31-3252a3609252",
            "__typename": "Text",
            "value": "Transform01",
            "source": None,
            "owner": None,
            "is_visible": True,
            "is_protected": False,
        },
        "url": {
            "id": "c02141df-52d7-4295-823f-1fda0896344b",
            "__typename": "Text",
            "value": "mytransform",
            "source": None,
            "owner": None,
            "is_visible": True,
            "is_protected": False,
        },
        "name": {
            "id": "41c4a6e0-b951-476d-a449-ca252a9db851",
            "__typename": "Text",
            "value": "transform01",
            "source": None,
            "owner": None,
            "is_visible": True,
            "is_protected": False,
        },
        "label": {
            "id": "e28f56f6-ac4d-4fdf-b5d2-9cf2dd9ad6bd",
            "__typename": "Text",
            "value": "Transform01",
            "source": None,
            "owner": None,
            "is_visible": True,
            "is_protected": False,
        },
        "description": {
            "id": "e287d237-18a2-4e50-9e06-e562cb822b02",
            "__typename": "Text",
            "source": None,
            "owner": None,
            "is_visible": True,
            "is_protected": False,
        },
        "timeout": {
            "id": "f9acd2fe-d535-48c6-9f3e-cdc4b430b3b5",
            "__typename": "Number",
            "value": 10,
            "source": None,
            "owner": None,
            "is_visible": True,
            "is_protected": False,
        },
        "rebase": {
            "id": "f557cafd-7da0-4c79-b582-378d9f02767e",
            "__typename": "Boolean",
            "value": False,
            "source": None,
            "owner": None,
            "is_visible": True,
            "is_protected": False,
        },
        "__typename": "CoreTransformPython",
        "display_label": "transform01",
    }
    return data


@pytest.fixture
async def transformation_node_01(client, schema_02, transformation_data_01) -> InfrahubNode:
    schema = [model for model in schema_02.nodes if model.kind == "CoreTransformPython"][0]
    node = InfrahubNode(client=client, schema=schema, data=transformation_data_01)
    return node


@pytest.fixture
async def transformation_data_02() -> dict:
    data = {
        "id": "70a58c98-6185-4004-b4bf-713baccfdc87",
        "display_label": "device_startup",
        "template_path": {"value": "template01.tpl.j2", "__typename": "TextAttribute"},
        "name": {"value": "mytemplate", "__typename": "TextAttribute"},
        "label": {"value": "My Rendered File", "__typename": "TextAttribute"},
        "description": {"value": "", "__typename": "TextAttribute"},
        "timeout": {"value": 10, "__typename": "NumberAttribute"},
        "rebase": {"value": False, "__typename": "CheckboxAttribute"},
        "query": {
            "node": {
                "id": "47800bff-adf1-450d-8388-b04ef2ffb129",
                "display_label": "query02",
                "__typename": InfrahubKind.GRAPHQLQUERY,
            },
            "__typename": f"NestedEdged{InfrahubKind.GRAPHQLQUERY}",
        },
        "repository": {
            "node": {
                "id": "7d1ee159-97c7-4787-8728-e10f998d0122",
                "display_label": "test-repo",
                "__typename": InfrahubKind.REPOSITORY,
            },
            "__typename": f"NestedEdged{InfrahubKind.REPOSITORY}",
        },
        "__typename": InfrahubKind.TRANSFORMJINJA2,
    }
    return data


@pytest.fixture
async def transformation_node_02(client, schema_02, transformation_data_02) -> InfrahubNode:
    schema = [model for model in schema_02.nodes if model.kind == InfrahubKind.TRANSFORMJINJA2][0]
    node = InfrahubNode(client=client, schema=schema, data=transformation_data_02)
    return node


@pytest.fixture
async def car_data_01() -> dict:
    data = {
        "id": "b663d7a4-5f95-48dd-b04d-e03169e7fcf3",
        "type": "TestElectricCar",
        "nbr_engine": {
            "id": "f6ec8006-cd76-436a-8d68-dec052cc3ff1",
            "__typename": "Number",
            "value": 2,
            "source": None,
            "owner": None,
            "is_visible": True,
            "is_protected": False,
        },
        "name": {
            "id": "8614f59a-c6ac-469d-96c8-feaa2a773013",
            "__typename": "Text",
            "value": "bolt",
            "source": None,
            "owner": None,
            "is_visible": True,
            "is_protected": False,
        },
        "nbr_seats": {
            "id": "943e9eca-34c1-4823-a591-27f02d159087",
            "__typename": "Number",
            "value": 2,
            "source": None,
            "owner": None,
            "is_visible": True,
            "is_protected": False,
        },
        "color": {
            "id": "064005b8-5182-4452-ba0c-7215bfc73cc6",
            "__typename": "Text",
            "value": "#444444",
            "source": None,
            "owner": None,
            "is_visible": True,
            "is_protected": False,
        },
        "__typename": "TestElectricCar",
        "display_label": "TestElectricCar(ID: b663d7a4-5f95-48dd-b04d-e03169e7fcf3)",
    }
    return data


@pytest.fixture
async def car_node_01(client, schema_02, car_data_01) -> InfrahubNode:
    schema = [model for model in schema_02.nodes if model.name == "ElectricCar"][0]
    node = InfrahubNode(client=client, schema=schema, data=car_data_01)
    return node


@pytest.fixture
async def mock_create_artifact(httpx_mock: HTTPXMock) -> HTTPXMock:
    response = {"data": {"CoreArtifactCreate": {"ok": True, "object": {"id": "8927425e-fd89-482a-bcec-aad267eb2c66"}}}}

    httpx_mock.add_response(
        method="POST", json=response, match_headers={"X-Infrahub-Tracker": "mutation-coreartifact-create"}
    )
    return httpx_mock


@pytest.fixture
async def mock_update_artifact(httpx_mock: HTTPXMock) -> HTTPXMock:
    response = {"data": {"CoreArtifactUpdate": {"ok": True, "object": {"id": "0d9a10bd-77f3-4388-a2fb-3cff9586cbb8"}}}}

    httpx_mock.add_response(
        method="POST", json=response, match_headers={"X-Infrahub-Tracker": "mutation-coreartifact-update"}
    )
    return httpx_mock
