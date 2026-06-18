from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub import config
from infrahub.core.initialization import create_branch
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase


@dataclass
class AtBeforeCreationCase:
    name: str
    query_branch_name: str | None


async def test_graphql_endpoint_with_timestamp(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers: dict[str, str],
    default_branch: Branch,
    create_test_admin: Node,
    car_person_data: dict[str, Node],
) -> None:
    time_before = Timestamp()

    p1 = car_person_data["p1"]
    p1.name.value = "Johnny"
    await p1.save(db=db)

    query = """
    query {
        TestPerson {
            edges {
                node {
                    name {
                        value
                    }
                }
            }
        }
    }
    """

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.post("/graphql", json={"query": query}, headers=admin_headers)

    assert response.status_code == 200
    assert "errors" not in response.json()
    assert response.json()["data"] is not None
    result = response.json()["data"]

    names = [result["node"]["name"]["value"] for result in result["TestPerson"]["edges"]]

    assert sorted(names) == ["Jane", "Johnny"]

    with client:
        response = client.post(f"/graphql?at={time_before.to_string()}", json={"query": query}, headers=admin_headers)

    assert response.status_code == 200
    assert "errors" not in response.json()
    assert response.json()["data"] is not None
    result = response.json()["data"]

    names = [result["node"]["name"]["value"] for result in result["TestPerson"]["edges"]]

    assert sorted(names) == ["Jane", "John"]


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(c, id=c.name)
        for c in [
            AtBeforeCreationCase(name="default_branch", query_branch_name=None),
            AtBeforeCreationCase(name="user_branch_origin_main", query_branch_name="user-branch"),
        ]
    ],
)
async def test_graphql_endpoint_at_before_branch_creation(
    case: AtBeforeCreationCase,
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers: dict[str, str],
    default_branch: Branch,
    create_test_admin: Node,
    car_person_data: dict[str, Node],
) -> None:
    """Querying with an `at` earlier than the default branch's creation must produce a clear, user-facing error.

    Since every user branch is currently rooted on the default branch, the error always references the default
    branch — directly for default-branch queries and indirectly (via the origin) for user-branch queries.
    """
    if case.query_branch_name is not None:
        user_branch = await create_branch(branch_name=case.query_branch_name, db=db)
        assert user_branch.get_created_at() != default_branch.get_created_at(), (
            "Test precondition: the user branch must be created at a distinct time from its origin "
            "so the boundary lookup picks a different value in each parametrized case"
        )

    at_before_creation = Timestamp("2000-01-01T00:00:00Z")
    assert at_before_creation < Timestamp(default_branch.get_created_at()), (
        "Test precondition: the chosen `at` must be earlier than the (origin) branch's created_at"
    )

    query = """
    query {
        TestPerson {
            edges {
                node {
                    name {
                        value
                    }
                }
            }
        }
    }
    """

    url_branch_suffix = f"/{case.query_branch_name}" if case.query_branch_name else ""
    with client:
        response = client.post(
            f"/graphql{url_branch_suffix}?at={at_before_creation.to_string()}",
            json={"query": query},
            headers=admin_headers,
        )

    expected_message = (
        f"Requested time '{at_before_creation.to_string()}' is before "
        f"branch '{default_branch.name}' was created at '{default_branch.get_created_at()}'."
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["message"] == expected_message


@pytest.mark.xfail(reason="Need to investigate, Currently working alone but failing when it's part of the test suite")
async def test_graphql_endpoint_generics(
    db: InfrahubDatabase,
    default_branch: Branch,
    client: TestClient,
    client_headers: dict[str, str],
    car_person_data_generic: dict[str, Node],
) -> None:
    query = """
    query {
        TestPerson {
            name {
                value
            }
            cars {
                name {
                    value
                }
            }
        }
    }
    """

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.post(
            "/graphql",
            json={"query": query},
            headers=client_headers,
        )

    assert response.status_code == 200
    assert "errors" not in response.json()
    assert response.json()["data"] is not None
    result = response.json()["data"]

    result_per_name = {result["name"]["value"]: result for result in result["TestPerson"]}

    assert sorted(result_per_name.keys()) == ["Jane", "John"]
    assert len(result_per_name["John"]["cars"]) == 2
    assert len(result_per_name["Jane"]["cars"]) == 1


@pytest.mark.parametrize("allow_anonymous_access", [False, True])
async def test_download_schema_anonymous_account(
    db: InfrahubDatabase, client: TestClient, client_headers: dict[str, str], allow_anonymous_access: bool
) -> None:
    await create_branch(branch_name="branch2", db=db)

    config.SETTINGS.main.allow_anonymous_access = allow_anonymous_access

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.get("/schema.graphql")
        assert response.status_code == 200 if allow_anonymous_access else 401


@pytest.mark.parametrize("allow_anonymous_access", [False, True])
async def test_download_graphql_schema_sorted(
    db: InfrahubDatabase, client: TestClient, client_headers: dict[str, str], allow_anonymous_access: bool
) -> None:
    config.SETTINGS.main.allow_anonymous_access = allow_anonymous_access

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.get("/schema.graphql?sorted=true")
        assert response.text
        assert response.status_code == 200 if allow_anonymous_access else 401
