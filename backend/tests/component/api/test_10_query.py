from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.utils import dict_hash

from infrahub import config
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreGraphQLQueryGroup
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


@pytest.fixture
async def base_authentication(
    db: InfrahubDatabase, default_branch: Branch, create_test_admin: Node, register_core_models_schema: SchemaBranch
) -> None:
    pass


async def read_query_group(db: InfrahubDatabase, query_name: str, params: dict[str, str]) -> CoreGraphQLQueryGroup:
    group = await NodeManager.get_one_by_default_filter(
        db=db, id=f"{query_name}__{dict_hash(params)}", kind=CoreGraphQLQueryGroup
    )
    assert group is not None
    return group


async def test_query_endpoint_group_no_params(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers: dict[str, str],
    default_branch: Branch,
    create_test_admin: Node,
    car_person_data: dict[str, Node],
) -> None:
    q1 = car_person_data["q1"]
    p1 = car_person_data["p1"]
    p2 = car_person_data["p2"]
    c1 = car_person_data["c1"]
    c2 = car_person_data["c2"]
    c3 = car_person_data["c3"]

    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.get(
            f"/api/query/query01?update_group=true&subscribers={c1.id}&subscribers={c2.id}", headers=admin_headers
        )

    assert "errors" not in response.json()
    assert response.status_code == 200
    assert response.json()["data"] is not None
    result = response.json()["data"]

    result_per_name = {result["node"]["name"]["value"]: result for result in result["TestPerson"]["edges"]}
    assert sorted(result_per_name.keys()) == ["Jane", "John"]
    assert len(result_per_name["John"]["node"]["cars"]["edges"]) == 2
    assert len(result_per_name["Jane"]["node"]["cars"]["edges"]) == 1

    group = await read_query_group(db=db, query_name="query01", params={})
    assert group.group_type.value.value == "internal"
    query = await group.query.get_peer(db=db)
    assert query is not None
    assert query.id == q1.id
    assert sorted(await group.members.get_peers(db=db)) == sorted([p1.id, p2.id, c1.id, c2.id, c3.id])
    assert sorted(await group.subscribers.get_peers(db=db)) == sorted([c1.id, c2.id])


async def test_query_endpoint_group_params(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers: dict[str, str],
    default_branch: Branch,
    create_test_admin: Node,
    car_person_data: dict[str, Node],
) -> None:
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.get("/api/query/query02?update_group=true&person=John", headers=admin_headers)

    assert "errors" not in response.json()
    assert response.status_code == 200
    assert response.json()["data"] is not None
    result = response.json()["data"]

    result_per_name = {result["node"]["name"]["value"]: result for result in result["TestPerson"]["edges"]}
    assert sorted(result_per_name.keys()) == ["John"]

    group = await read_query_group(db=db, query_name="query02", params={"person": "John"})
    assert group.parameters.value == {"person": "John"}
    assert sorted(await group.members.get_peers(db=db)) == [car_person_data["p1"].id]
    assert await group.subscribers.get_peers(db=db) == {}


async def test_query_endpoint_group_update_keeps_one_group_per_query_and_params(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers: dict[str, str],
    default_branch: Branch,
    create_test_admin: Node,
    car_person_data: dict[str, Node],
) -> None:
    c1 = car_person_data["c1"]
    c2 = car_person_data["c2"]

    with client:
        for subscriber in (c1, c2):
            response = client.get(
                f"/api/query/query02?update_group=true&person=John&subscribers={subscriber.id}", headers=admin_headers
            )
            assert response.status_code == 200

    groups = await NodeManager.query(db=db, schema=InfrahubKind.GRAPHQLQUERYGROUP)
    assert len(groups) == 1
    group = await read_query_group(db=db, query_name="query02", params={"person": "John"})
    assert sorted(await group.subscribers.get_peers(db=db)) == sorted([c1.id, c2.id])


async def test_query_endpoint_get_default_branch(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers: dict[str, str],
    default_branch: Branch,
    create_test_admin: Node,
    car_person_data: dict[str, Node],
) -> None:
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
    admin_headers: dict[str, str],
    default_branch: Branch,
    car_person_data: dict[str, Node],
    base_authentication: None,
) -> None:
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
    admin_headers: dict[str, str],
    default_branch: Branch,
    car_person_data: dict[str, Node],
    base_authentication: None,
) -> None:
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
    admin_headers: dict[str, str],
    default_branch: Branch,
    create_test_admin: Node,
    car_person_data: dict[str, Node],
    authentication_base: Node,
) -> None:
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
    client_headers: dict[str, str],
    default_branch: Branch,
    car_person_schema: SchemaBranch,
    register_core_models_schema: SchemaBranch,
) -> None:
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
    client_headers: dict[str, str],
    default_branch: Branch,
    car_person_schema: SchemaBranch,
    register_core_models_schema: SchemaBranch,
) -> None:
    # Must execute in a with block to execute the startup/shutdown events
    with client:
        response = client.get(
            "/api/query/query01?branch=notvalid",
            headers=client_headers,
        )

    assert response.status_code == 400


async def test_query_endpoint_at_before_branch_creation(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers: dict[str, str],
    default_branch: Branch,
    create_test_admin: Node,
    car_person_data: dict[str, Node],
) -> None:
    at_before_creation = Timestamp("2000-01-01T00:00:00Z")
    assert at_before_creation < Timestamp(default_branch.get_created_at()), (
        "Test precondition: the chosen `at` must be earlier than the branch's created_at"
    )

    with client:
        response = client.get(
            f"/api/query/query01?at={at_before_creation.to_string()}",
            headers=admin_headers,
        )

    expected_message = (
        f"Requested time '{at_before_creation.to_string()}' is before "
        f"branch '{default_branch.name}' was created at '{default_branch.get_created_at()}'."
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["message"] == expected_message


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
    assert "You do not have one of the following permissions" in error["errors"][0]["message"]


@pytest.mark.parametrize("allow_anonymous_access", [False, True])
async def test_query_endpoint_anonymous_account(
    db: InfrahubDatabase,
    client: TestClient,
    default_branch: Branch,
    car_person_data: dict[str, Node],
    allow_anonymous_access: bool,
) -> None:
    config.SETTINGS.main.allow_anonymous_access = allow_anonymous_access

    with client:
        response = client.get("/api/query/query01")

    # 403 when access is allowed is fine, due to missing permission
    assert response.status_code == 403 if allow_anonymous_access else 401
