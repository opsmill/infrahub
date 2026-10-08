from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING, Any

from graphql import GraphQLError

from infrahub import config
from infrahub.graphql.cost.first_step import FirstStepCounter
from infrahub.graphql.cost.service import QueryCostEstimator
from infrahub.graphql.cost.statistics_store import StatisticsSnapshotHolder, StatisticsStore
from infrahub.log import get_logger

if TYPE_CHECKING:
    from graphql import GraphQLSchema

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase
    from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
    from infrahub.graphql.cost.models import QueryEstimate
    from infrahub.services.adapters.cache import InfrahubCache

log = get_logger()


@cache
def get_statistics_snapshot_holder() -> StatisticsSnapshotHolder:
    """Return the statistics the process loaded last, shared by every request the process handles."""
    return StatisticsSnapshotHolder()


def build_query_cost_estimator(
    db: InfrahubDatabase,
    branch: Branch,
    at: Timestamp,
    reads_current_time: bool,
    schema_branch: SchemaBranch,
    cache: InfrahubCache,
) -> QueryCostEstimator:
    """Build the estimator of the queries of one request.

    Args:
        at: Time the request reads, used by the queries that count its first step.
        reads_current_time: The request gives no time of its own.

    """
    return QueryCostEstimator(
        counter=FirstStepCounter(
            db=db,
            branch=branch,
            at=at,
            schema_branch=schema_branch,
            query_size_limit=config.SETTINGS.database.query_size_limit,
        ),
        store=StatisticsStore(cache=cache),
        snapshot_holder=get_statistics_snapshot_holder(),
        schema_branch=schema_branch,
        branch=branch,
        reads_current_time=reads_current_time,
    )


async def estimate_request_cost(
    estimator: QueryCostEstimator,
    analyzer: InfrahubGraphQLQueryAnalyzer,
    schema: GraphQLSchema,
    variable_values: dict[str, Any],
) -> QueryEstimate | None:
    """Estimate the cost of the query of a request, or return None when no estimate can be computed.

    The request runs and returns the same data and errors whether or not its cost can be estimated, so a failure
    leaves the cost details without an estimate rather than failing the request.
    """
    try:
        return await estimator.estimate(analyzer=analyzer, schema=schema, variable_values=variable_values)
    except GraphQLError:
        # The variables or the arguments are invalid, and running the query returns that error to the client.
        return None
    except Exception:
        # A best-effort side effect: the statistics cache or a counting query failing must not fail the request.
        log.exception("The cost of the GraphQL query could not be estimated, the cost details have no estimate")
        return None
