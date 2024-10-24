from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.initialization import create_branch
from infrahub.message_bus import messages

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase


@pytest.fixture
async def base_authentication(
    db: InfrahubDatabase, default_branch: Branch, create_test_admin, register_core_models_schema
) -> None:
    pass


async def test_query_endpoint_group_no_params(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers,
    create_test_admin,
    default_branch,
    car_person_data,
    patch_services,
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.get(
            "/api/query/query01?update_group=true&subscribers=AAAAAA&subscribers=BBBBBB", headers=admin_headers
        )

    assert "errors" not in response.json()
    assert response.status_code == 200
    assert response.json()["data"] is not None
    result = response.json()["data"]

    result_per_name = {result["node"]["name"]["value"]: result for result in result["TestPerson"]["edges"]}
    assert sorted(result_per_name.keys()) == ["Jane", "John"]
    assert len(result_per_name["John"]["node"]["cars"]["edges"]) == 2
    assert len(result_per_name["Jane"]["node"]["cars"]["edges"]) == 1

    q1 = car_person_data["q1"]
    p1 = car_person_data["p1"]
    p2 = car_person_data["p2"]
    c1 = car_person_data["c1"]
    c2 = car_person_data["c2"]
    c3 = car_person_data["c3"]

    assert (
        messages.RequestGraphQLQueryGroupUpdate(
            query_id=q1.id,
            query_name="query01",
            branch="main",
            related_node_ids=sorted([p1.id, p2.id, c1.id, c2.id, c3.id]),
            subscribers=sorted(["AAAAAA", "BBBBBB"]),
            params={},
        )
        in client.app.state.service.message_bus.messages
    )


async def test_query_endpoint_group_params(
    db: InfrahubDatabase, client: TestClient, admin_headers, default_branch, create_test_admin, car_person_data
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.get("/api/query/query02?update_group=true&person=John", headers=admin_headers)

    assert "errors" not in response.json()
    assert response.status_code == 200
    assert response.json()["data"] is not None
    result = response.json()["data"]

    result_per_name = {result["node"]["name"]["value"]: result for result in result["TestPerson"]["edges"]}
    assert sorted(result_per_name.keys()) == ["John"]

    q2 = car_person_data["q2"]
    p1 = car_person_data["p1"]

    assert (
        messages.RequestGraphQLQueryGroupUpdate(
            query_id=q2.id,
            query_name="query02",
            branch="main",
            related_node_ids={p1.id},
            subscribers=[],
            params={"person": "John"},
        )
        in client.app.state.service.message_bus.messages
    )


async def test_query_endpoint_get_default_branch(
    db: InfrahubDatabase, client: TestClient, admin_headers, default_branch, create_test_admin, car_person_data
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.get("/api/query/query01", headers=admin_headers)

    assert "errors" not in response.json()
    assert response.status_code == 200
    assert response.json()["data"] is not None
    result = response.json()["data"]

    result_per_name = {result["node"]["name"]["value"]: result for result in result["TestPerson"]["edges"]}
    assert sorted(result_per_name.keys()) == ["Jane", "John"]
    assert len(result_per_name["John"]["node"]["cars"]["edges"]) == 2
    assert len(result_per_name["Jane"]["node"]["cars"]["edges"]) == 1


async def test_query_endpoint_post_no_payload(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers,
    default_branch,
    car_person_data,
    base_authentication,
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.post(
            "/api/query/query01",
            headers=admin_headers,
        )

    assert "errors" not in response.json()
    assert response.status_code == 200
    assert response.json()["data"] is not None
    result = response.json()["data"]

    result_per_name = {result["node"]["name"]["value"]: result for result in result["TestPerson"]["edges"]}
    assert sorted(result_per_name.keys()) == ["Jane", "John"]
    assert len(result_per_name["John"]["node"]["cars"]["edges"]) == 2
    assert len(result_per_name["Jane"]["node"]["cars"]["edges"]) == 1


async def test_query_endpoint_post_with_params(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers,
    default_branch,
    car_person_data,
    base_authentication,
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.post("/api/query/query02", headers=admin_headers, json={"variables": {"person": "John"}})

    assert "errors" not in response.json()
    assert response.status_code == 200
    assert response.json()["data"] is not None
    result = response.json()["data"]

    result_per_name = {result["node"]["name"]["value"]: result for result in result["TestPerson"]["edges"]}
    assert sorted(result_per_name.keys()) == ["John"]


async def test_query_endpoint_branch1(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers,
    default_branch,
    create_test_admin,
    car_person_data,
    authentication_base,
):
    await create_branch(branch_name="branch1", db=db)

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.get("/api/query/query01?branch=branch1", headers=admin_headers)

    assert "errors" not in response.json()
    assert response.status_code == 200
    assert response.json()["data"] is not None
    result = response.json()["data"]

    result_per_name = {result["node"]["name"]["value"]: result for result in result["TestPerson"]["edges"]}
    assert sorted(result_per_name.keys()) == ["Jane", "John"]
    assert len(result_per_name["John"]["node"]["cars"]["edges"]) == 2
    assert len(result_per_name["Jane"]["node"]["cars"]["edges"]) == 1


async def test_query_endpoint_wrong_query(
    db: InfrahubDatabase,
    client: TestClient,
    client_headers,
    default_branch,
    car_person_schema,
    register_core_models_schema,
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.get(
            "/api/query/query99",
            headers=client_headers,
        )

    assert response.status_code == 404


async def test_query_endpoint_wrong_branch(
    db: InfrahubDatabase,
    client: TestClient,
    client_headers,
    default_branch,
    car_person_schema,
    register_core_models_schema,
):
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.get(
            "/api/query/query01?branch=notvalid",
            headers=client_headers,
        )

    assert response.status_code == 400


async def test_query_endpoint_missing_privs(
    db: InfrahubDatabase,
    client: TestClient,
    first_account: Node,
    default_branch: Branch,
    car_person_data: dict[str, Node],
    base_authentication: None,
) -> None:
    with client:
        token = client.post(
            "/api/auth/login", json={"username": first_account.name.value, "password": first_account.password.value}
        )
        assert token.status_code == 200
        access_token = token.json()["access_token"]

        response = client.post(
            "/api/query/query01",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert response.status_code == 403
    error = response.json()
    assert error["errors"]
    assert "You do not have the following permission" in error["errors"][0]["message"]
