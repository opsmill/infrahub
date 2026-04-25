from __future__ import annotations

from typing import TYPE_CHECKING

from graphene import Boolean, Field, ObjectType, String

from infrahub.core import registry
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql.initialization import GraphqlContext


class GraphQLQueryReport(ObjectType):
    targets_unique_nodes = Field(
        Boolean,
        required=True,
        description=(
            "True if every operation in the submitted query resolves to uniquely identifiable nodes "
            "(via a required ids argument or a required field matching the model uniqueness constraints). "
            "When true, Infrahub limits artifact regeneration to only the nodes that changed. "
            "When false, all artifacts for the definition are regenerated on any relevant node change."
        ),
    )


async def resolve_graphql_query_report(
    _root: None,
    info: GraphQLResolveInfo,
    query: str,
) -> dict[str, bool]:
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

    return {"targets_unique_nodes": analyzer.query_report.only_has_unique_targets}


InfrahubGraphQLQueryReport = Field(
    GraphQLQueryReport,
    query=String(required=True, description="The raw GraphQL query string to analyze."),
    description="Analyze a GraphQL query string and return a report describing how Infrahub will interpret it.",
    resolver=resolve_graphql_query_report,
    required=True,
)
