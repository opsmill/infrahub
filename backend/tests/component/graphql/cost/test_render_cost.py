from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub import config
from infrahub.core.constants import GraphQLQueryCostLevel
from infrahub.graphql.cost.render_cost import LIGHT_RENDER, RenderCostClassifier
from infrahub.graphql.cost.tasks import refresh_query_cost_statistics

if TYPE_CHECKING:
    import pytest

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from tests.adapters.cache import MemoryCache

PERSON_CARS_QUERY = """
query PersonCars($name: String!) {
    TestPerson(name__value: $name) {
        edges {
            node {
                name { value }
                cars { edges { node { name { value } } } }
            }
        }
    }
}
"""


async def test_renders_for_targets_with_many_peers_are_high_cost(
    default_branch: Branch,
    car_fleet: dict[str, Node],
    memory_cache: MemoryCache,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await refresh_query_cost_statistics()
    monkeypatch.setattr(config.SETTINGS.graphql_cost, "limit_high_cost_renders", True)
    monkeypatch.setattr(config.SETTINGS.graphql_cost, "high_cost_database_rows", 10)

    classifier = await RenderCostClassifier.for_stored_query(
        branch_name=default_branch.name, query=PERSON_CARS_QUERY, cost_level=GraphQLQueryCostLevel.HIGH.value
    )
    carol = await classifier.classify(variables={"name": "Carol"})
    alice = await classifier.classify(variables={"name": "Alice"})

    # 3 database rows for the person and for each of its cars.
    assert carol.high_cost
    assert carol.worst_case_database_rows == 3 + 5 * 3
    assert not alice.high_cost
    assert alice.worst_case_database_rows == 3


async def test_renders_of_a_query_without_the_high_level_are_light(
    default_branch: Branch,
    car_fleet: dict[str, Node],
    memory_cache: MemoryCache,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await refresh_query_cost_statistics()
    monkeypatch.setattr(config.SETTINGS.graphql_cost, "limit_high_cost_renders", True)
    monkeypatch.setattr(config.SETTINGS.graphql_cost, "high_cost_database_rows", 10)

    classifier = await RenderCostClassifier.for_stored_query(
        branch_name=default_branch.name, query=PERSON_CARS_QUERY, cost_level=GraphQLQueryCostLevel.LOW.value
    )

    assert await classifier.classify(variables={"name": "Carol"}) == LIGHT_RENDER


async def test_renders_are_light_when_the_limit_is_disabled(
    default_branch: Branch,
    car_fleet: dict[str, Node],
    memory_cache: MemoryCache,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await refresh_query_cost_statistics()
    monkeypatch.setattr(config.SETTINGS.graphql_cost, "high_cost_database_rows", 10)

    classifier = await RenderCostClassifier.for_stored_query(
        branch_name=default_branch.name, query=PERSON_CARS_QUERY, cost_level=GraphQLQueryCostLevel.HIGH.value
    )

    assert await classifier.classify(variables={"name": "Carol"}) == LIGHT_RENDER


async def test_a_render_without_statistics_is_high_cost(
    default_branch: Branch,
    car_fleet: dict[str, Node],
    memory_cache: MemoryCache,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config.SETTINGS.graphql_cost, "limit_high_cost_renders", True)

    classifier = await RenderCostClassifier.for_stored_query(
        branch_name=default_branch.name, query=PERSON_CARS_QUERY, cost_level=GraphQLQueryCostLevel.HIGH.value
    )
    render = await classifier.classify(variables={"name": "Alice"})

    assert render.high_cost
    assert render.worst_case_database_rows is None
