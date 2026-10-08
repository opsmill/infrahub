from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest
from neo4j.exceptions import TransientError

from infrahub import config
from tests.component.graphql.cost.helpers import ADMIN_HEADERS, QUERY_COST_HEADERS, get_counting_database
from tests.helpers.db_query_counter import CountingInfrahubDatabase

if TYPE_CHECKING:
    from collections.abc import Generator

    from fastapi.testclient import TestClient
    from neo4j import Record

    from infrahub.core.node import Node
    from infrahub.core.query import QueryType

FAILING_QUERY_NAME = "relationship_get_peer"

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


@dataclass
class PlannedFailure:
    query_name: str | None = None


class FailingOnceDatabase(CountingInfrahubDatabase):
    """Raise a transient error the next time a query of the planned name runs."""

    def __init__(self, planned_failure: PlannedFailure | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # shared by reference so that a failure planned on the application database reaches its sessions
        self.planned_failure = planned_failure if planned_failure is not None else PlannedFailure()

    def get_context(self) -> dict[str, Any]:
        context = super().get_context()
        context["planned_failure"] = self.planned_failure
        return context

    def fail_next(self, query_name: str) -> None:
        self.planned_failure.query_name = query_name

    async def execute_query_with_metadata(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        name: str = "undefined",
        context: dict[str, str] | None = None,
        type: QueryType | None = None,
        timeout_seconds: float | None = None,
    ) -> tuple[list[Record], dict[str, Any]]:
        if name == self.planned_failure.query_name:
            self.planned_failure.query_name = None
            raise TransientError(f"the query {name} failed once")
        return await super().execute_query_with_metadata(
            query=query, params=params, name=name, context=context, type=type, timeout_seconds=timeout_seconds
        )


@pytest.fixture
def counting_database_class() -> type[CountingInfrahubDatabase]:
    return FailingOnceDatabase


@pytest.fixture
def three_attempts() -> Generator[None, None, None]:
    original_retry_limit = config.SETTINGS.database.retry_limit
    config.SETTINGS.database.retry_limit = 3
    yield
    config.SETTINGS.database.retry_limit = original_retry_limit


async def test_retried_resolver_calls_are_counted(
    counting_client: TestClient, car_fleet: dict[str, Node], three_attempts: None
) -> None:
    with counting_client:
        database = get_counting_database(client=counting_client)
        assert isinstance(database, FailingOnceDatabase)
        database.fail_next(query_name=FAILING_QUERY_NAME)
        with_header = counting_client.post("/graphql", json={"query": PERSONS_CARS_QUERY}, headers=QUERY_COST_HEADERS)
        without_header = counting_client.post("/graphql", json={"query": PERSONS_CARS_QUERY}, headers=ADMIN_HEADERS)

    assert database.planned_failure.query_name is None
    assert with_header.status_code == 200
    assert "errors" not in with_header.json()
    assert with_header.json()["data"] == without_header.json()["data"]
    actual_counts = {
        field["path"]: {"nodes": field["actual"]["nodes"], "resolver_calls": field["actual"]["resolver_calls"]}
        for field in with_header.json()["extensions"]["query_cost"]["fields"]
    }
    # The three calls of the batch that failed are retried, and each attempt counts as a call.
    assert actual_counts == {
        "TestPerson": {"nodes": 3, "resolver_calls": 1},
        "TestPerson/cars": {"nodes": 7, "resolver_calls": 6},
    }
