from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from infrahub import config
from infrahub.core.constants import GraphQLQueryCostLevel, RelationshipCardinality
from infrahub.graphql.cost.high_cost_request import HighCostRequest, find_high_cost_request
from infrahub.graphql.cost.models import (
    CostFigures,
    EstimateMode,
    EstimateSource,
    FieldDescription,
    FieldEstimate,
    QueryEstimate,
    StatisticsPointer,
)

if TYPE_CHECKING:
    from collections.abc import Generator

HIGH = GraphQLQueryCostLevel.HIGH.value


def _query_estimate(worst_case_rows: int) -> QueryEstimate:
    return QueryEstimate(
        mode=EstimateMode.COUNTED_FIRST_STEP,
        statistics=StatisticsPointer(
            version=1,
            branch="main",
            computed_at=datetime(2026, 10, 11, 4, 0, tzinfo=UTC),
            schema_hash="9f3c0a7e5d1b",
            kinds=("TestPerson",),
        ),
        estimates={
            "TestPerson": FieldEstimate(
                field=FieldDescription(
                    kind="TestPerson", relationship_identifier=None, cardinality=RelationshipCardinality.MANY
                ),
                expected=CostFigures(nodes=1, resolver_calls=1, database_rows=worst_case_rows // 10),
                worst_case=CostFigures(nodes=1, resolver_calls=1, database_rows=worst_case_rows),
                source=EstimateSource.COUNTED,
                worst_case_is_bound=True,
                reason=None,
            )
        },
    )


@pytest.fixture
def pipelined_runtime_enabled() -> Generator[None]:
    settings = config.SETTINGS.graphql_cost
    original = (settings.pipelined_runtime_for_high_cost_queries, settings.high_cost_database_rows)
    settings.pipelined_runtime_for_high_cost_queries = True
    settings.high_cost_database_rows = 1_000
    yield
    settings.pipelined_runtime_for_high_cost_queries, settings.high_cost_database_rows = original


@pytest.mark.usefixtures("pipelined_runtime_enabled")
async def test_request_above_the_limit_is_high_cost() -> None:
    estimate = AsyncMock(return_value=_query_estimate(worst_case_rows=1_001))

    assert await find_high_cost_request(cost_level=HIGH, estimate=estimate) == HighCostRequest(
        worst_case_database_rows=1_001
    )


@pytest.mark.usefixtures("pipelined_runtime_enabled")
async def test_request_at_or_below_the_limit_is_not_high_cost() -> None:
    estimate = AsyncMock(return_value=_query_estimate(worst_case_rows=1_000))

    assert await find_high_cost_request(cost_level=HIGH, estimate=estimate) is None


@pytest.mark.usefixtures("pipelined_runtime_enabled")
async def test_request_that_cannot_be_estimated_is_high_cost() -> None:
    estimate = AsyncMock(return_value=None)

    assert await find_high_cost_request(cost_level=HIGH, estimate=estimate) == HighCostRequest(
        worst_case_database_rows=None
    )


@pytest.mark.usefixtures("pipelined_runtime_enabled")
@pytest.mark.parametrize("cost_level", [GraphQLQueryCostLevel.LOW.value, GraphQLQueryCostLevel.UNKNOWN.value, None])
async def test_request_to_a_query_without_the_high_level_is_not_estimated(cost_level: str | None) -> None:
    estimate = AsyncMock(return_value=_query_estimate(worst_case_rows=1_000_000))

    assert await find_high_cost_request(cost_level=cost_level, estimate=estimate) is None
    estimate.assert_not_awaited()


async def test_request_is_not_estimated_when_the_setting_is_disabled() -> None:
    estimate = AsyncMock(return_value=_query_estimate(worst_case_rows=1_000_000))

    assert await find_high_cost_request(cost_level=HIGH, estimate=estimate) is None
    estimate.assert_not_awaited()
