from __future__ import annotations

from typing import TYPE_CHECKING

from tests.component.graphql.cost.helpers import ADMIN_HEADERS, QUERY_COST_HEADERS, get_counting_database

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from infrahub.core.node import Node

# A `count` under a cardinality-many field awaits its own query before the peer loader runs, which makes the
# number of loader batches, and so of queries, differ between identical requests.
PERSONS_CARS_OWNERS_QUERY = """
query {
    TestPerson {
        count
        edges {
            node {
                name { value }
                display_label
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


async def test_header_adds_no_query_other_than_the_estimate_queries(
    counting_client: TestClient, car_fleet: dict[str, Node]
) -> None:
    with counting_client:
        database = get_counting_database(client=counting_client)
        warm_up = counting_client.post("/graphql", json={"query": PERSONS_CARS_OWNERS_QUERY}, headers=ADMIN_HEADERS)

        database.reset_counts()
        without_header = counting_client.post(
            "/graphql", json={"query": PERSONS_CARS_OWNERS_QUERY}, headers=ADMIN_HEADERS
        )
        queries_without_header = database.query_counts.total()

        database.reset_counts()
        with_header = counting_client.post(
            "/graphql", json={"query": PERSONS_CARS_OWNERS_QUERY}, headers=QUERY_COST_HEADERS
        )
        queries_with_header = database.query_counts.total()

    for response in (warm_up, without_header, with_header):
        assert response.status_code == 200
        assert "errors" not in response.json()
    estimate_queries = with_header.json()["extensions"]["query_cost"]["estimate_queries"]["queries"]
    assert queries_without_header > 0
    assert queries_without_header == queries_with_header - estimate_queries
