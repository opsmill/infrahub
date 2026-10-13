from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub import config
from infrahub.core.constants import GraphQLQueryCostLevel
from infrahub.core.registry import registry
from infrahub.core.timestamp import Timestamp
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.cost.request_estimate import build_query_cost_estimator, estimate_request_cost
from infrahub.graphql.cost.stored_query import classify_query_estimate
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.workers.dependencies import get_cache, get_database

if TYPE_CHECKING:
    from graphql import GraphQLSchema

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from infrahub.services.adapters.cache import InfrahubCache


@dataclass(frozen=True, slots=True)
class RenderCost:
    high_cost: bool
    worst_case_database_rows: int | None
    """Worst-case database rows estimated for the target; None when the render was not estimated."""


LIGHT_RENDER = RenderCost(high_cost=False, worst_case_database_rows=None)


@dataclass(frozen=True, slots=True)
class _QueryContext:
    db: InfrahubDatabase
    branch: Branch
    schema_branch: SchemaBranch
    graphql_schema: GraphQLSchema
    analyzer: InfrahubGraphQLQueryAnalyzer
    cache: InfrahubCache


class RenderCostClassifier:
    """Decide which renders of one stored query, each for one target, are high-cost.

    Only the renders of a query whose stored cost level is high are estimated, once for each target with the
    target's variable values, so the top-level nodes and their peers are counted for that target.
    """

    def __init__(self, query_context: _QueryContext | None, high_cost_database_rows: int) -> None:
        self.query_context = query_context
        self.high_cost_database_rows = high_cost_database_rows

    @classmethod
    async def for_stored_query(cls, branch_name: str, query: str, cost_level: str | None) -> RenderCostClassifier:
        """Prepare the classification of the renders of a stored query on a branch.

        Every render is light when the limit of high-cost renders is disabled or when the stored cost level of
        the query is not high.
        """
        settings = config.SETTINGS.graphql_cost
        if not settings.limit_high_cost_renders or cost_level != GraphQLQueryCostLevel.HIGH.value:
            return cls(query_context=None, high_cost_database_rows=settings.high_cost_database_rows)

        db = await get_database()
        branch = await registry.get_branch(db=db, branch=branch_name)
        schema_branch = registry.schema.get_schema_branch(name=branch.name)
        graphql_params = await prepare_graphql_params(db=db, branch=branch)
        analyzer = InfrahubGraphQLQueryAnalyzer(
            query=query, schema=graphql_params.schema, branch=branch, schema_branch=schema_branch
        )
        return cls(
            query_context=_QueryContext(
                db=db,
                branch=branch,
                schema_branch=schema_branch,
                graphql_schema=graphql_params.schema,
                analyzer=analyzer,
                cache=await get_cache(),
            ),
            high_cost_database_rows=settings.high_cost_database_rows,
        )

    async def classify(self, variables: dict[str, Any]) -> RenderCost:
        """Estimate the render for one target; a render that cannot be estimated counts as high-cost."""
        context = self.query_context
        if context is None:
            return LIGHT_RENDER

        estimator = build_query_cost_estimator(
            db=context.db,
            branch=context.branch,
            at=Timestamp(),
            reads_current_time=True,
            schema_branch=context.schema_branch,
            cache=context.cache,
        )
        query_estimate = await estimate_request_cost(
            estimator=estimator, analyzer=context.analyzer, schema=context.graphql_schema, variable_values=variables
        )
        if query_estimate is None:
            return RenderCost(high_cost=True, worst_case_database_rows=None)
        cost = classify_query_estimate(
            query_estimate=query_estimate, high_cost_database_rows=self.high_cost_database_rows
        )
        worst_case_rows = cost.worst_case.database_rows if cost.worst_case else None
        return RenderCost(high_cost=cost.level != GraphQLQueryCostLevel.LOW, worst_case_database_rows=worst_case_rows)
