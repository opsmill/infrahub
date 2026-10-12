from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

import pytest

from infrahub import config
from infrahub.api import query as query_api
from infrahub.constants.database import Neo4jRuntime
from infrahub.core.constants import GraphQLQueryCostLevel, InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.graphql.cost.runtime import replace_parallel_runtime
from infrahub.graphql.cost.tasks import refresh_query_cost_statistics

if TYPE_CHECKING:
    from collections.abc import Generator, Iterator

    from fastapi.testclient import TestClient

    from infrahub.database import InfrahubDatabase
    from tests.adapters.cache import MemoryCache

CARS_OF_PERSON_QUERY = """
query($person: String!) {
    TestPerson(name__value: $person) {
        edges {
            node {
                name { value }
                cars { edges { node { name { value } } } }
            }
        }
    }
}
"""


async def _stored_query(db: InfrahubDatabase, cost_level: str) -> Node:
    query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
    await query.new(db=db, name="cars_of_person", query=CARS_OF_PERSON_QUERY, cost_level=cost_level)
    await query.save(db=db)
    return query


async def _set_cost_level(db: InfrahubDatabase, query: Node, cost_level: str) -> None:
    stored = await NodeManager.get_one(db=db, id=query.id)
    assert stored
    stored.get_attribute("cost_level").value = cost_level
    await stored.save(db=db, fields=["cost_level"])


@pytest.fixture
async def high_cost_query(db: InfrahubDatabase, create_test_admin: Node, car_person_data: dict[str, Node]) -> Node:
    return await _stored_query(db=db, cost_level=GraphQLQueryCostLevel.HIGH.value)


@pytest.fixture
async def low_cost_query(db: InfrahubDatabase, create_test_admin: Node, car_person_data: dict[str, Node]) -> Node:
    return await _stored_query(db=db, cost_level=GraphQLQueryCostLevel.LOW.value)


@pytest.fixture
def pipelined_runtime_enabled() -> Generator[None]:
    settings = config.SETTINGS.graphql_cost
    original = settings.pipelined_runtime_for_high_cost_queries
    settings.pipelined_runtime_for_high_cost_queries = True
    yield
    settings.pipelined_runtime_for_high_cost_queries = original


@pytest.fixture
def replaced_runtimes(monkeypatch: pytest.MonkeyPatch) -> list[Neo4jRuntime]:
    """Runtimes that the stored query endpoint ran a GraphQL query with, in place of the parallel runtime."""
    entered: list[Neo4jRuntime] = []

    @contextmanager
    def recording_replacement(runtime: Neo4jRuntime) -> Iterator[None]:
        entered.append(runtime)
        with replace_parallel_runtime(runtime):
            yield

    monkeypatch.setattr(query_api, "replace_parallel_runtime", recording_replacement)
    return entered


def _cars_of_john(client: TestClient, admin_headers: dict[str, str]) -> list[str]:
    with client:
        response = client.get("/api/query/cars_of_person?person=John", headers=admin_headers)
    assert response.status_code == 200
    cars = response.json()["data"]["TestPerson"]["edges"][0]["node"]["cars"]["edges"]
    return sorted(car["node"]["name"]["value"] for car in cars)


@pytest.mark.usefixtures("pipelined_runtime_enabled", "high_cost_query")
async def test_request_above_the_limit_runs_with_the_pipelined_runtime(
    client: TestClient,
    admin_headers: dict[str, str],
    memory_cache: MemoryCache,
    replaced_runtimes: list[Neo4jRuntime],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # With a limit of one row, the refresh keeps the high level of the stored query.
    monkeypatch.setattr(config.SETTINGS.graphql_cost, "high_cost_database_rows", 1)
    await refresh_query_cost_statistics()

    assert _cars_of_john(client=client, admin_headers=admin_headers) == ["bolt", "volt"]
    assert replaced_runtimes == [Neo4jRuntime.PIPELINED]


@pytest.mark.usefixtures("pipelined_runtime_enabled")
async def test_request_below_the_limit_keeps_the_configured_runtime(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers: dict[str, str],
    memory_cache: MemoryCache,
    high_cost_query: Node,
    replaced_runtimes: list[Neo4jRuntime],
) -> None:
    await refresh_query_cost_statistics()
    # The refresh sets the level from the statistics; the request is estimated only with the high level.
    await _set_cost_level(db=db, query=high_cost_query, cost_level=GraphQLQueryCostLevel.HIGH.value)

    assert _cars_of_john(client=client, admin_headers=admin_headers) == ["bolt", "volt"]
    assert replaced_runtimes == []


@pytest.mark.usefixtures("pipelined_runtime_enabled", "high_cost_query")
async def test_request_that_cannot_be_estimated_runs_with_the_pipelined_runtime(
    client: TestClient, admin_headers: dict[str, str], replaced_runtimes: list[Neo4jRuntime]
) -> None:
    # Without statistics, the fields below the first step have no estimate.
    assert _cars_of_john(client=client, admin_headers=admin_headers) == ["bolt", "volt"]
    assert replaced_runtimes == [Neo4jRuntime.PIPELINED]


@pytest.mark.usefixtures("pipelined_runtime_enabled", "low_cost_query")
async def test_request_to_a_low_cost_query_keeps_the_configured_runtime(
    client: TestClient, admin_headers: dict[str, str], replaced_runtimes: list[Neo4jRuntime]
) -> None:
    assert _cars_of_john(client=client, admin_headers=admin_headers) == ["bolt", "volt"]
    assert replaced_runtimes == []


@pytest.mark.usefixtures("high_cost_query")
async def test_request_keeps_the_configured_runtime_when_the_setting_is_disabled(
    client: TestClient, admin_headers: dict[str, str], replaced_runtimes: list[Neo4jRuntime]
) -> None:
    assert _cars_of_john(client=client, admin_headers=admin_headers) == ["bolt", "volt"]
    assert replaced_runtimes == []
