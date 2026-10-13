from __future__ import annotations

from datetime import datetime  # noqa: TC003  (pydantic needs it at runtime)
from typing import TYPE_CHECKING

from pydantic import BaseModel, ValidationError

from infrahub import config
from infrahub.core.constants import GraphQLQueryCostLevel, InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.timestamp import Timestamp
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.cost.constants import NO_STATISTICS_REASON
from infrahub.graphql.cost.request_estimate import build_query_cost_estimator, estimate_request_cost
from infrahub.graphql.initialization import prepare_graphql_params

if TYPE_CHECKING:
    from graphql import GraphQLSchema

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from infrahub.graphql.cost.models import CostFigures, QueryEstimate
    from infrahub.services.adapters.cache import InfrahubCache

MUTATION_REASON = "the query contains a mutation"
ESTIMATE_FAILED_REASON = "the cost could not be estimated"
COSTLIEST_FIELDS_LIMIT = 3


class StoredCostFigures(BaseModel):
    nodes: int
    resolver_calls: int
    database_rows: int


class StoredFieldCost(BaseModel):
    path: str
    expected_database_rows: int
    worst_case_database_rows: int


class StoredQueryCost(BaseModel):
    """Estimate of one run of a stored query, as the `cost_estimate` attribute of the query holds it."""

    level: GraphQLQueryCostLevel
    reason: str | None = None
    """Why the level is unknown."""

    high_cost_database_rows: int
    """Limit of estimated database rows that the level was compared with."""

    statistics_computed_at: datetime | None = None
    statistics_version: int | None = None
    expected: StoredCostFigures | None = None
    worst_case: StoredCostFigures | None = None
    """Figures summed over the fields that have an estimate."""

    fields_without_estimate: int = 0
    costliest_fields: list[StoredFieldCost] = []
    """Fields with the most worst-case database rows, most first."""

    def same_estimate_as(self, stored: object) -> bool:
        """Whether a stored `cost_estimate` value gives the same level and figures, whatever statistics computed it."""
        if not isinstance(stored, dict):
            return False
        try:
            other = StoredQueryCost.model_validate(stored)
        except ValidationError:
            return False
        ignored = {"statistics_computed_at", "statistics_version"}
        return self.model_dump(exclude=ignored) == other.model_dump(exclude=ignored)


def unknown_cost(reason: str) -> StoredQueryCost:
    return StoredQueryCost(
        level=GraphQLQueryCostLevel.UNKNOWN,
        reason=reason,
        high_cost_database_rows=config.SETTINGS.graphql_cost.high_cost_database_rows,
    )


def _summed(figures: list[CostFigures]) -> StoredCostFigures:
    return StoredCostFigures(
        nodes=sum(item.nodes for item in figures),
        resolver_calls=sum(item.resolver_calls for item in figures),
        database_rows=sum(item.database_rows for item in figures),
    )


def classify_query_estimate(query_estimate: QueryEstimate, high_cost_database_rows: int) -> StoredQueryCost:
    """Sum the estimate of each field and compare the worst-case database rows with the limit.

    The worst case of a query filtered on one target reflects the target with the most peers, while the
    expected figures reflect a target with the average number of peers at each step.
    """
    estimated = [
        (path, field_estimate)
        for path, field_estimate in query_estimate.estimates.items()
        if field_estimate.expected is not None and field_estimate.worst_case is not None
    ]
    without_estimate = len(query_estimate.estimates) - len(estimated)
    statistics = query_estimate.statistics
    if statistics is None or not estimated:
        return StoredQueryCost(
            level=GraphQLQueryCostLevel.UNKNOWN,
            reason=NO_STATISTICS_REASON,
            high_cost_database_rows=high_cost_database_rows,
            statistics_computed_at=statistics.computed_at if statistics else None,
            statistics_version=statistics.version if statistics else None,
            fields_without_estimate=without_estimate,
        )

    expected = _summed([field_estimate.expected for _, field_estimate in estimated if field_estimate.expected])
    worst_case = _summed([field_estimate.worst_case for _, field_estimate in estimated if field_estimate.worst_case])
    costliest = sorted(
        (
            StoredFieldCost(
                path=path,
                expected_database_rows=field_estimate.expected.database_rows,
                worst_case_database_rows=field_estimate.worst_case.database_rows,
            )
            for path, field_estimate in estimated
            if field_estimate.expected is not None and field_estimate.worst_case is not None
        ),
        key=lambda field: field.worst_case_database_rows,
        reverse=True,
    )[:COSTLIEST_FIELDS_LIMIT]
    level = (
        GraphQLQueryCostLevel.HIGH if worst_case.database_rows > high_cost_database_rows else GraphQLQueryCostLevel.LOW
    )
    return StoredQueryCost(
        level=level,
        high_cost_database_rows=high_cost_database_rows,
        statistics_computed_at=statistics.computed_at,
        statistics_version=statistics.version,
        expected=expected,
        worst_case=worst_case,
        fields_without_estimate=without_estimate,
        costliest_fields=costliest,
    )


async def estimate_stored_query_cost(
    db: InfrahubDatabase,
    branch: Branch,
    schema_branch: SchemaBranch,
    graphql_schema: GraphQLSchema,
    query: str,
    cache: InfrahubCache,
) -> StoredQueryCost:
    """Estimate one run of a stored query from the statistics alone, since a stored query has no variable values.

    Never raises for a query that cannot be estimated: the level is then unknown with a reason.
    """
    analyzer = InfrahubGraphQLQueryAnalyzer(
        query=query, schema=graphql_schema, branch=branch, schema_branch=schema_branch
    )
    valid, _ = analyzer.is_valid
    if not valid:
        return unknown_cost(reason=ESTIMATE_FAILED_REASON)
    if analyzer.contains_mutation:
        return unknown_cost(reason=MUTATION_REASON)

    estimator = build_query_cost_estimator(
        db=db, branch=branch, at=Timestamp(), reads_current_time=True, schema_branch=schema_branch, cache=cache
    )
    query_estimate = await estimate_request_cost(
        estimator=estimator, analyzer=analyzer, schema=graphql_schema, variable_values=None
    )
    if query_estimate is None:
        return unknown_cost(reason=ESTIMATE_FAILED_REASON)
    return classify_query_estimate(
        query_estimate=query_estimate,
        high_cost_database_rows=config.SETTINGS.graphql_cost.high_cost_database_rows,
    )


async def refresh_stored_query_costs(db: InfrahubDatabase, branch: Branch, cache: InfrahubCache) -> int:
    """Estimate every stored query of the branch again and save the estimates that changed.

    Returns:
        The number of stored queries whose estimate changed.

    """
    schema_branch = db.schema.get_schema_branch(name=branch.name)
    graphql_params = await prepare_graphql_params(db=db, branch=branch)
    queries = await NodeManager.query(db=db, schema=InfrahubKind.GRAPHQLQUERY, branch=branch)
    updated = 0
    for stored_query in queries:
        query = stored_query.get_attribute("query").value
        if not isinstance(query, str):
            continue
        cost = await estimate_stored_query_cost(
            db=db,
            branch=branch,
            schema_branch=schema_branch,
            graphql_schema=graphql_params.schema,
            query=query,
            cache=cache,
        )
        level = stored_query.get_attribute("cost_level")
        estimate = stored_query.get_attribute("cost_estimate")
        if level.get_value() == cost.level.value and cost.same_estimate_as(estimate.value):
            continue
        level.value = cost.level.value
        estimate.value = cost.model_dump(mode="json")
        await stored_query.save(db=db, fields=["cost_level", "cost_estimate"])
        updated += 1
    return updated
