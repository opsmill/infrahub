from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tests.component.graphql.cost.helpers import ADMIN_HEADERS, QUERY_COST_HEADERS, get_counting_database

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from infrahub.core.node import Node

PERSONS_CARS_OWNERS_QUERY = """
query {
    TestPerson {
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

PERSONS_CARS_QUERY = """
query {
    TestPerson {
        edges {
            node {
                name { value }
                cars { edges { node { name { value } } } }
            }
        }
    }
}
"""

PERSONS_CARS_WITH_CAR_LABELS_AND_COUNT_QUERY = """
query {
    TestPerson {
        edges {
            node {
                name { value }
                cars { count edges { node { name { value } display_label } } }
            }
        }
    }
}
"""

PERSONS_WITH_LABELS_AND_COUNT_CARS_QUERY = """
query {
    TestPerson {
        count
        edges {
            node {
                name { value }
                display_label
                cars { edges { node { name { value } } } }
            }
        }
    }
}
"""

TYPENAME_QUERY = "query { __typename }"

UPDATE_PERSON_MUTATION = """
mutation($id: String!) {
    TestPersonUpdate(data: {id: $id, height: {value: 182}}) {
        ok
        object { id height { value } }
    }
}
"""


def post_query(client: TestClient, query: str, headers: dict[str, str]) -> dict[str, Any]:
    response = client.post("/graphql", json={"query": query}, headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert "errors" not in payload
    return payload


def rows_by_path(payload: dict[str, Any]) -> dict[str, int]:
    return {field["path"]: field["actual"]["database_rows"] for field in payload["extensions"]["query_cost"]["fields"]}


def recorded_rows(payload: dict[str, Any]) -> int:
    query_cost = payload["extensions"]["query_cost"]
    return (
        sum(field["actual"]["database_rows"] for field in query_cost["fields"])
        + query_cost["estimate_queries"]["database_rows"]
        + query_cost["unattributed"]["database_rows"]
    )


def post_and_count_rows(client: TestClient, query: str) -> tuple[dict[str, Any], int]:
    """Post a query with the header and return the response and every row its request read."""
    database = get_counting_database(client=client)
    database.reset_counts()
    payload = post_query(client=client, query=query, headers=QUERY_COST_HEADERS)
    return payload, database.row_counts.total()


async def test_response_without_the_header_has_no_extensions(
    counting_client: TestClient, car_fleet: dict[str, Node]
) -> None:
    with counting_client:
        payload = post_query(client=counting_client, query=PERSONS_CARS_OWNERS_QUERY, headers=ADMIN_HEADERS)

    assert list(payload) == ["data"]


async def test_details_leave_the_data_unchanged(counting_client: TestClient, car_fleet: dict[str, Node]) -> None:
    with counting_client:
        without_header = post_query(client=counting_client, query=PERSONS_CARS_OWNERS_QUERY, headers=ADMIN_HEADERS)
        with_header = post_query(client=counting_client, query=PERSONS_CARS_OWNERS_QUERY, headers=QUERY_COST_HEADERS)

    assert list(with_header) == ["data", "extensions"]
    assert list(with_header["extensions"]) == ["query_cost"]
    assert with_header["data"] == without_header["data"]
    assert len(with_header["data"]["TestPerson"]["edges"]) == 3


async def test_details_count_the_nodes_and_resolver_calls_of_each_field(
    counting_client: TestClient, car_fleet: dict[str, Node]
) -> None:
    with counting_client:
        payload = post_query(client=counting_client, query=PERSONS_CARS_OWNERS_QUERY, headers=QUERY_COST_HEADERS)

    query_cost = payload["extensions"]["query_cost"]
    no_statistics = {
        "expected": None,
        "worst_case": None,
        "worst_case_is_bound": False,
        "source": None,
        "reason": "no statistics",
    }
    assert query_cost["estimate_mode"] == "statistics_only"
    assert query_cost["statistics"] is None
    assert query_cost["estimate_queries"] == {"queries": 0, "database_rows": 0}
    assert [
        {key: value for key, value in field.items() if key != "actual"}
        | {"nodes": field["actual"]["nodes"], "resolver_calls": field["actual"]["resolver_calls"]}
        for field in query_cost["fields"]
    ] == [
        {
            "path": "TestPerson",
            "kind": "TestPerson",
            "relationship_identifier": None,
            "cardinality": "many",
            "estimate": no_statistics,
            "nodes": 3,
            "resolver_calls": 1,
        },
        {
            "path": "TestPerson/cars",
            "kind": "TestCar",
            "relationship_identifier": "testcar__testperson",
            "cardinality": "many",
            "estimate": no_statistics,
            "nodes": 7,
            "resolver_calls": 3,
        },
        {
            "path": "TestPerson/cars/owner",
            "kind": "TestPerson",
            "relationship_identifier": "testcar__testperson",
            "cardinality": "one",
            "estimate": no_statistics,
            "nodes": 7,
            "resolver_calls": 7,
        },
    ]
    assert all(field["actual"]["database_rows"] > 0 for field in query_cost["fields"])


async def test_details_account_for_every_row_the_request_reads(
    counting_client: TestClient, car_fleet: dict[str, Node]
) -> None:
    with counting_client:
        post_query(client=counting_client, query=PERSONS_CARS_OWNERS_QUERY, headers=ADMIN_HEADERS)
        # Authentication and permission loading read before the handler can tell a query from a mutation, and
        # those reads depend only on the account, so a request that resolves no field measures them.
        baseline, baseline_rows = post_and_count_rows(client=counting_client, query=TYPENAME_QUERY)
        payload, rows_read = post_and_count_rows(client=counting_client, query=PERSONS_CARS_OWNERS_QUERY)

    rows_read_before_the_recorder = baseline_rows - recorded_rows(payload=baseline)
    assert baseline["extensions"]["query_cost"]["fields"] == []
    assert rows_read_before_the_recorder > 0
    assert recorded_rows(payload=payload) > 0
    assert recorded_rows(payload=payload) == rows_read - rows_read_before_the_recorder


async def test_count_and_display_label_reads_are_counted_for_the_fields_that_read_them(
    counting_client: TestClient, car_fleet: dict[str, Node]
) -> None:
    with counting_client:
        post_query(client=counting_client, query=PERSONS_CARS_QUERY, headers=ADMIN_HEADERS)
        base, base_rows = post_and_count_rows(client=counting_client, query=PERSONS_CARS_QUERY)
        car_reads, car_reads_rows = post_and_count_rows(
            client=counting_client, query=PERSONS_CARS_WITH_CAR_LABELS_AND_COUNT_QUERY
        )
        person_reads, person_reads_rows = post_and_count_rows(
            client=counting_client, query=PERSONS_WITH_LABELS_AND_COUNT_CARS_QUERY
        )

    base_by_path = rows_by_path(payload=base)
    car_reads_by_path = rows_by_path(payload=car_reads)
    person_reads_by_path = rows_by_path(payload=person_reads)

    assert car_reads_rows > base_rows
    assert car_reads_by_path == {
        "TestPerson": base_by_path["TestPerson"],
        "TestPerson/cars": base_by_path["TestPerson/cars"] + car_reads_rows - base_rows,
    }
    assert car_reads["extensions"]["query_cost"]["unattributed"] == base["extensions"]["query_cost"]["unattributed"]

    assert person_reads_rows > base_rows
    assert person_reads_by_path == {
        "TestPerson": base_by_path["TestPerson"] + person_reads_rows - base_rows,
        "TestPerson/cars": base_by_path["TestPerson/cars"],
    }
    assert person_reads["extensions"]["query_cost"]["unattributed"] == base["extensions"]["query_cost"]["unattributed"]


async def test_mutation_with_the_header_returns_the_response_without_the_header(
    counting_client: TestClient, car_fleet: dict[str, Node]
) -> None:
    person_id = car_fleet["Bob"].id
    request = {"query": UPDATE_PERSON_MUTATION, "variables": {"id": person_id}}

    with counting_client:
        without_header = counting_client.post("/graphql", json=request, headers=ADMIN_HEADERS)
        with_header = counting_client.post("/graphql", json=request, headers=QUERY_COST_HEADERS)

    assert without_header.status_code == 200
    assert with_header.status_code == 200
    assert with_header.json() == without_header.json()
    assert with_header.json() == {
        "data": {"TestPersonUpdate": {"ok": True, "object": {"id": person_id, "height": {"value": 182}}}}
    }
