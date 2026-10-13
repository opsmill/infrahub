from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub import config
from infrahub.core.constants import GraphQLQueryCostLevel
from infrahub.core.manager import NodeManager
from infrahub.graphql.cost.constants import NO_STATISTICS_REASON
from infrahub.graphql.cost.stored_query import MUTATION_REASON, refresh_stored_query_costs
from infrahub.graphql.cost.tasks import refresh_query_cost_statistics
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql

if TYPE_CHECKING:
    import pytest

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase
    from tests.adapters.cache import MemoryCache

CREATE_STORED_QUERY = """
mutation CreateStoredQuery($name: String!, $query: String!) {
    CoreGraphQLQueryCreate(data: {name: {value: $name}, query: {value: $query}}) {
        ok
        object { id }
    }
}
"""

PERSONS_CARS_QUERY = """
query PersonsCars {
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

CREATE_PERSON_MUTATION = """
mutation CreatePerson {
    TestPersonCreate(data: {name: {value: "Dave"}}) { ok }
}
"""


async def _create_stored_query(db: InfrahubDatabase, branch: Branch, name: str, query: str) -> Node:
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=CREATE_STORED_QUERY,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"name": name, "query": query},
    )
    assert result.errors is None
    assert result.data
    stored_query = await NodeManager.get_one(db=db, id=result.data["CoreGraphQLQueryCreate"]["object"]["id"])
    assert stored_query
    return stored_query


def _level(stored_query: Node) -> str:
    level = stored_query.get_attribute("cost_level").get_value()
    assert isinstance(level, str)
    return level


def _estimate(stored_query: Node) -> dict[str, Any]:
    estimate = stored_query.get_attribute("cost_estimate").value
    assert isinstance(estimate, dict)
    return estimate


async def test_stored_query_cost_is_unknown_before_the_first_refresh(
    db: InfrahubDatabase, default_branch: Branch, car_fleet: dict[str, Node], memory_cache: MemoryCache
) -> None:
    stored_query = await _create_stored_query(db=db, branch=default_branch, name="persons", query=PERSONS_CARS_QUERY)

    assert _level(stored_query) == GraphQLQueryCostLevel.UNKNOWN.value
    assert _estimate(stored_query)["reason"] == NO_STATISTICS_REASON
    assert _estimate(stored_query)["worst_case"] is None


async def test_refresh_estimates_the_stored_queries_of_the_default_branch(
    db: InfrahubDatabase, default_branch: Branch, car_fleet: dict[str, Node], memory_cache: MemoryCache
) -> None:
    stored_query = await _create_stored_query(db=db, branch=default_branch, name="persons", query=PERSONS_CARS_QUERY)

    await refresh_query_cost_statistics()

    refreshed = await NodeManager.get_one(db=db, id=stored_query.id)
    assert refreshed
    assert _level(refreshed) == GraphQLQueryCostLevel.LOW.value
    estimate = _estimate(refreshed)
    assert estimate["reason"] is None
    assert estimate["statistics_version"] == 1
    assert estimate["fields_without_estimate"] == 0
    # The query reads all 3 persons and their 7 cars, so the worst case is the expected case:
    # 3 database rows for each person and each car.
    assert estimate["expected"] == {"nodes": 3 + 7, "resolver_calls": 1 + 3, "database_rows": 9 + 21}
    assert estimate["worst_case"] == estimate["expected"]
    assert [field["path"] for field in estimate["costliest_fields"]] == ["TestPerson/cars", "TestPerson"]


async def test_stored_query_above_the_limit_has_the_high_level(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_fleet: dict[str, Node],
    memory_cache: MemoryCache,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await refresh_query_cost_statistics()
    monkeypatch.setattr(config.SETTINGS.graphql_cost, "high_cost_database_rows", 10)

    stored_query = await _create_stored_query(db=db, branch=default_branch, name="persons", query=PERSONS_CARS_QUERY)

    assert _level(stored_query) == GraphQLQueryCostLevel.HIGH.value
    assert _estimate(stored_query)["high_cost_database_rows"] == 10
    assert _estimate(stored_query)["worst_case"]["database_rows"] > 10


async def test_stored_mutation_has_an_unknown_cost(
    db: InfrahubDatabase, default_branch: Branch, car_fleet: dict[str, Node], memory_cache: MemoryCache
) -> None:
    await refresh_query_cost_statistics()

    stored_query = await _create_stored_query(
        db=db, branch=default_branch, name="create_person", query=CREATE_PERSON_MUTATION
    )

    assert _level(stored_query) == GraphQLQueryCostLevel.UNKNOWN.value
    assert _estimate(stored_query)["reason"] == MUTATION_REASON


async def test_refresh_saves_only_the_estimates_that_changed(
    db: InfrahubDatabase,
    default_branch: Branch,
    car_fleet: dict[str, Node],
    memory_cache: MemoryCache,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _create_stored_query(db=db, branch=default_branch, name="persons", query=PERSONS_CARS_QUERY)
    await refresh_query_cost_statistics()

    assert await refresh_stored_query_costs(db=db, branch=default_branch, cache=memory_cache) == 0

    monkeypatch.setattr(config.SETTINGS.graphql_cost, "high_cost_database_rows", 10)
    assert await refresh_stored_query_costs(db=db, branch=default_branch, cache=memory_cache) == 1
