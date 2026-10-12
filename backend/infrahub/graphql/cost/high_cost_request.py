from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub import config
from infrahub.core.constants import GraphQLQueryCostLevel
from infrahub.graphql.cost.stored_query import classify_query_estimate

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from infrahub.graphql.cost.models import QueryEstimate

PIPELINED_RUNTIME_MESSAGE = "with the pipelined Cypher runtime"


@dataclass(frozen=True, slots=True)
class HighCostRequest:
    worst_case_database_rows: int | None
    """Worst-case database rows estimated for the request; None when the request could not be estimated."""


async def find_high_cost_request(
    cost_level: str | None, estimate: Callable[[], Awaitable[QueryEstimate | None]]
) -> HighCostRequest | None:
    """Decide whether a request to a stored query is high-cost, so that it runs with the pipelined runtime.

    The request is estimated with its own variables only when the pipelined runtime for high-cost queries is
    enabled and the stored cost level of the query is high. It is high-cost when its worst-case database rows are
    above the limit, or when it cannot be estimated. Returns None for every other request.
    """
    settings = config.SETTINGS.graphql_cost
    if not settings.pipelined_runtime_for_high_cost_queries or cost_level != GraphQLQueryCostLevel.HIGH.value:
        return None
    query_estimate = await estimate()
    if query_estimate is None:
        return HighCostRequest(worst_case_database_rows=None)
    cost = classify_query_estimate(
        query_estimate=query_estimate, high_cost_database_rows=settings.high_cost_database_rows
    )
    if cost.level == GraphQLQueryCostLevel.LOW:
        return None
    return HighCostRequest(worst_case_database_rows=cost.worst_case.database_rows if cost.worst_case else None)
