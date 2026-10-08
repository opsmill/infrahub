from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from httpx import Response

    from infrahub.database import InfrahubDatabase

QUERY_COST_HEADER = {"X-Infrahub-Query-Cost": "details"}

CARS_OF_PERSON_QUERY = """
query($person: String!) {
    TestPerson(name__value: $person) {
        edges {
            node {
                name { value }
                cars {
                    edges {
                        node {
                            name { value }
                            owner { node { name { value } } }
                        }
                    }
                }
            }
        }
    }
}
"""

EXPECTED_ACTUAL_COUNTS = {
    "TestPerson": {"nodes": 1, "resolver_calls": 1},
    "TestPerson/cars": {"nodes": 2, "resolver_calls": 1},
    "TestPerson/cars/owner": {"nodes": 2, "resolver_calls": 2},
}


@pytest.fixture
async def cars_of_person_query(db: InfrahubDatabase, create_test_admin: Node, car_person_data: dict[str, Node]) -> Node:
    query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
    await query.new(db=db, name="cars_of_person", query=CARS_OF_PERSON_QUERY)
    await query.save(db=db)
    return query


def actual_counts_by_path(payload: dict[str, Any]) -> dict[str, dict[str, int]]:
    return {
        field["path"]: {"nodes": field["actual"]["nodes"], "resolver_calls": field["actual"]["resolver_calls"]}
        for field in payload["extensions"]["query_cost"]["fields"]
    }


def assert_same_data_with_details_only_on_request(without_header: Response, with_header: Response) -> None:
    assert without_header.status_code == 200
    assert with_header.status_code == 200
    assert list(without_header.json()) == ["data"]
    assert list(with_header.json()) == ["data", "extensions"]
    assert with_header.json()["data"] == without_header.json()["data"]
    cars = with_header.json()["data"]["TestPerson"]["edges"][0]["node"]["cars"]["edges"]
    assert sorted(car["node"]["name"]["value"] for car in cars) == ["bolt", "volt"]
    assert actual_counts_by_path(payload=with_header.json()) == EXPECTED_ACTUAL_COUNTS


async def test_get_stored_query_returns_the_details_only_with_the_header(
    client: TestClient, admin_headers: dict[str, str], cars_of_person_query: Node
) -> None:
    with client:
        without_header = client.get("/api/query/cars_of_person?person=John", headers=admin_headers)
        with_header = client.get("/api/query/cars_of_person?person=John", headers=admin_headers | QUERY_COST_HEADER)

    assert_same_data_with_details_only_on_request(without_header=without_header, with_header=with_header)


async def test_post_stored_query_returns_the_details_only_with_the_header(
    client: TestClient, admin_headers: dict[str, str], cars_of_person_query: Node
) -> None:
    payload = {"variables": {"person": "John"}}

    with client:
        without_header = client.post("/api/query/cars_of_person", json=payload, headers=admin_headers)
        with_header = client.post("/api/query/cars_of_person", json=payload, headers=admin_headers | QUERY_COST_HEADER)

    assert_same_data_with_details_only_on_request(without_header=without_header, with_header=with_header)
