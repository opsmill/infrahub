from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub import config
from infrahub.core.initialization import create_branch
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


async def test_graphql_endpoint(
    db: InfrahubDatabase, client: TestClient, admin_headers, default_branch: Branch, create_test_admin, car_person_data
) -> None:
    query = """
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

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.post("/graphql", json={"query": query}, headers=admin_headers)

    assert response.status_code == 200
    assert "errors" not in response.json()
    assert response.json()["data"] is not None
    result = response.json()["data"]

    result_per_name = {result["node"]["name"]["value"]: result for result in result["TestPerson"]["edges"]}

    assert sorted(result_per_name.keys()) == ["Jane", "John"]
    assert len(result_per_name["John"]["node"]["cars"]["edges"]) == 2
    assert len(result_per_name["Jane"]["node"]["cars"]["edges"]) == 1


async def test_graphql_endpoint_with_timestamp(
    db: InfrahubDatabase, client: TestClient, admin_headers, default_branch: Branch, create_test_admin, car_person_data
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


@pytest.mark.xfail(reason="Need to investigate, Currently working alone but failing when it's part of the test suite")
async def test_graphql_endpoint_generics(
    db: InfrahubDatabase, default_branch: Branch, client, client_headers, car_person_data_generic
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


async def test_graphql_options(
    db: InfrahubDatabase, client, client_headers, default_branch: Branch, car_person_data
) -> None:
    await create_branch(branch_name="branch2", db=db)

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.options(
            "/graphql",
            headers=client_headers,
        )

        assert response.status_code == 200
        assert "Allow" in response.headers
        assert response.headers["Allow"] == "GET, POST, OPTIONS"

        response = client.options(
            "/graphql/branch2",
            headers=client_headers,
        )

        assert response.status_code == 200
        assert "Allow" in response.headers
        assert response.headers["Allow"] == "GET, POST, OPTIONS"

        response = client.options(
            "/graphql/notvalid",
            headers=client_headers,
        )

        assert response.status_code == 404


async def test_read_profile(
    db: InfrahubDatabase,
    client,
    admin_headers,
    authentication_base,
) -> None:
    query = """
    query {
        AccountProfile {
            name {
                value
            }
        }
    }
    """

    with client:
        response = client.post(
            "/graphql",
            json={"query": query},
            headers=admin_headers,
        )

    assert response.status_code
    assert response.json() == {"data": {"AccountProfile": {"name": {"value": "test-admin"}}}}


async def test_download_schema(db: InfrahubDatabase, client, client_headers) -> None:
    await create_branch(branch_name="branch2", db=db)

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.get("/schema.graphql", headers=client_headers)
        assert response.status_code == 200

        response = client.get("/schema.graphql?branch=branch2", headers=client_headers)
        assert response.status_code == 200

        response = client.get("/schema.graphql?branch=notvalid", headers=client_headers)
        assert response.status_code == 400


@pytest.mark.parametrize("allow_anonymous_access", [False, True])
async def test_download_schema_anonymous_account(
    db: InfrahubDatabase, client, client_headers, allow_anonymous_access: bool
) -> None:
    await create_branch(branch_name="branch2", db=db)

    config.SETTINGS.main.allow_anonymous_access = allow_anonymous_access

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.get("/schema.graphql")
        assert response.status_code == 200 if allow_anonymous_access else 401


@pytest.mark.parametrize("allow_anonymous_access", [False, True])
async def test_download_graphql_schema_sorted(
    db: InfrahubDatabase, client, client_headers, allow_anonymous_access: bool
) -> None:
    config.SETTINGS.main.allow_anonymous_access = allow_anonymous_access

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.get("/schema.graphql?sorted=true")
        assert response.text
        assert response.status_code == 200 if allow_anonymous_access else 401
