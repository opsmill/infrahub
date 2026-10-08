from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from graphene import BigInt, Boolean, DateTime, Enum, Field, Int, List, NonNull, ObjectType, String
from graphene.types.generic import GenericScalar
from graphql import GraphQLError

from infrahub.core import registry
from infrahub.core.timestamp import Timestamp
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.cost.models import EstimateMode, EstimateSource
from infrahub.graphql.cost.request_estimate import build_query_cost_estimator
from infrahub.graphql.initialization import GraphqlParams

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.graphql.cost.models import FieldEstimate, QueryEstimate
    from infrahub.graphql.initialization import GraphqlContext

_ESTIMATE_MODE_DESCRIPTIONS = {
    EstimateMode.COUNTED_FIRST_STEP: (
        "The variables argument was given: the top-level nodes and the fields directly under them were counted."
    ),
    EstimateMode.STATISTICS_ONLY: (
        "The variables argument was not given: every figure comes from the statistics, and no counting query ran."
    ),
}


def _describe_estimate_mode(mode: EstimateMode | None) -> str:
    if mode is None:
        return "How the figures of the cost estimate were obtained."
    return _ESTIMATE_MODE_DESCRIPTIONS[mode]


GraphQLQueryCostEstimateMode = Enum.from_enum(
    EstimateMode, name="GraphQLQueryCostEstimateMode", description=_describe_estimate_mode
)

GraphQLQueryCostSource = Enum.from_enum(
    EstimateSource,
    name="GraphQLQueryCostSource",
    description="Where the figures of one field come from: counted on the request's branch and time, or the statistics.",
)


class GraphQLQueryCostStatistics(ObjectType):
    branch = String(required=True, description="Branch the statistics describe, always the default branch.")
    computed_at = DateTime(required=True, description="Time the statistics refresh started reading the branch.")
    version = Int(required=True)


class GraphQLQueryCostFigures(ObjectType):
    nodes = BigInt(required=True)
    resolver_calls = BigInt(required=True)
    database_rows = BigInt(required=True)


class GraphQLQueryFieldCostEstimate(ObjectType):
    path = String(
        required=True,
        description="Response keys from the top-level field, joined by '/', without edges, node and list indexes.",
    )
    kind = String(required=True)
    relationship_identifier = String(description="Relationship identifier; null for a top-level field.")
    cardinality = String(required=True, description="ONE or MANY; MANY for a top-level field.")
    expected = Field(GraphQLQueryCostFigures, description="Null when reason is set.")
    worst_case = Field(GraphQLQueryCostFigures, description="Null when reason is set.")
    worst_case_is_bound = Boolean(
        required=True,
        description="True when the worst case is an upper bound: statistics of the request's branch, no at time.",
    )
    source = Field(GraphQLQueryCostSource)
    reason = String(description="Why no estimate is given, for example 'no statistics'.")


class GraphQLQueryCostEstimate(ObjectType):
    mode = Field(GraphQLQueryCostEstimateMode, required=True)
    statistics = Field(GraphQLQueryCostStatistics, description="Null when no statistics exist yet.")
    fields = List(NonNull(GraphQLQueryFieldCostEstimate), required=True)


@dataclass(frozen=True, slots=True)
class AnalyzedQuery:
    """The query submitted to the report, analyzed once for every field of the report."""

    targets_unique_nodes: bool
    analyzer: InfrahubGraphQLQueryAnalyzer
    schema_branch: SchemaBranch
    variables: object
    """Value of the `variables` argument; None when the argument was not given."""


async def resolve_graphql_query_cost_estimate(
    analyzed: AnalyzedQuery, info: GraphQLResolveInfo
) -> GraphQLQueryCostEstimate:
    """Estimate the cost of the submitted query, for an account allowed to run it.

    Raises:
        GraphQLError: When the submitted query contains a mutation, when the variables are not an object or do not
            match the types the query declares, or when the offset or the limit of a top-level field is negative.
        PermissionDeniedError: When running the submitted query would be denied to the account.
        AuthorizationError: When running the submitted query would require the account to be authenticated.

    """
    # Imported here because the module of the checker imports the GraphQL schema, which imports this module.
    from infrahub.graphql.api.dependencies import build_graphql_query_permission_checker  # noqa: PLC0415

    graphql_context: GraphqlContext = info.context
    analyzer = analyzed.analyzer
    if analyzer.contains_mutation:
        raise GraphQLError("The cost estimate covers queries only.")

    await build_graphql_query_permission_checker().check(
        db=graphql_context.db,
        account_session=graphql_context.active_account_session,
        analyzed_query=analyzer,
        query_parameters=GraphqlParams(schema=info.schema, context=graphql_context),
        branch=graphql_context.branch,
    )

    variables = analyzed.variables
    if variables is not None and not isinstance(variables, dict):
        raise GraphQLError("The variables argument must be an object that maps each variable name to its value.")

    request = graphql_context.request
    estimator = build_query_cost_estimator(
        db=graphql_context.db,
        branch=graphql_context.branch,
        at=graphql_context.at if graphql_context.at is not None else Timestamp(),
        # Without a request, the time the context reads may have been given by the caller.
        reads_current_time=request is not None and request.query_params.get("at") is None,
        schema_branch=analyzed.schema_branch,
        cache=graphql_context.active_service.cache,
    )
    query_estimate = await estimator.estimate(analyzer=analyzer, schema=info.schema, variable_values=variables)
    return _describe_query_estimate(query_estimate=query_estimate)


def _describe_query_estimate(query_estimate: QueryEstimate) -> GraphQLQueryCostEstimate:
    return GraphQLQueryCostEstimate(
        mode=query_estimate.mode,
        statistics=query_estimate.statistics,
        fields=[
            _describe_field_estimate(path=path, field_estimate=field_estimate)
            for path, field_estimate in query_estimate.estimates.items()
        ],
    )


def _describe_field_estimate(path: str, field_estimate: FieldEstimate) -> GraphQLQueryFieldCostEstimate:
    return GraphQLQueryFieldCostEstimate(
        path=path,
        kind=field_estimate.field.kind,
        relationship_identifier=field_estimate.field.relationship_identifier,
        cardinality=field_estimate.field.cardinality.name,
        expected=field_estimate.expected,
        worst_case=field_estimate.worst_case,
        worst_case_is_bound=field_estimate.worst_case_is_bound,
        source=field_estimate.source,
        reason=field_estimate.reason,
    )


class GraphQLQueryReport(ObjectType):
    targets_unique_nodes = Field(
        Boolean,
        required=True,
        description=(
            "True if every operation in the submitted query resolves to uniquely identifiable nodes. "
            "An operation resolves uniquely when it filters by a required ids or hfid argument, or when "
            "every component of at least one of the model's uniqueness constraints is pinned by a required, "
            "single-valued argument. When true, Infrahub limits artifact regeneration to only the nodes that "
            "changed. When false, all artifacts for the definition are regenerated on any relevant node change."
        ),
    )
    cost_estimate = Field(
        GraphQLQueryCostEstimate,
        required=True,
        description=(
            "Estimated work of the submitted query for each field. Selecting this field requires read permission, "
            "on the request's branch, for every kind in the submitted query; otherwise the request fails with the "
            "permission error that running the query would return."
        ),
        resolver=resolve_graphql_query_cost_estimate,
    )


async def resolve_graphql_query_report(
    _root: None,
    info: GraphQLResolveInfo,
    query: str,
    variables: object = None,
) -> AnalyzedQuery:
    graphql_context: GraphqlContext = info.context
    branch = graphql_context.branch
    schema_branch = registry.schema.get_schema_branch(name=branch.name)

    analyzer = InfrahubGraphQLQueryAnalyzer(
        query=query,
        schema=info.schema,
        branch=branch,
        schema_branch=schema_branch,
    )

    is_valid, errors = analyzer.is_valid
    if not is_valid and errors:
        raise errors[0]

    return AnalyzedQuery(
        targets_unique_nodes=analyzer.query_report.only_has_unique_targets,
        analyzer=analyzer,
        schema_branch=schema_branch,
        variables=variables,
    )


InfrahubGraphQLQueryReport = Field(
    GraphQLQueryReport,
    query=String(required=True, description="The raw GraphQL query string to analyze."),
    variables=GenericScalar(
        required=False,
        description=(
            "Values of the variables the query declares. When given (an empty object counts), the first step is "
            "counted; when omitted, the estimate is statistics only."
        ),
    ),
    description="Analyze a GraphQL query string and return a report describing how Infrahub will interpret it.",
    resolver=resolve_graphql_query_report,
    required=True,
)
