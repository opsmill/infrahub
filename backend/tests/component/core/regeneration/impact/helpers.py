from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from tests.constants import TestKind

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.graphql.analyzer import GraphQLQueryReport

# The car is the group member; the tag stands in for an artifact or generator definition. The impact
# mapping reads only the subscriber's id and typename, so a plain kind keeps the fixture free of the
# transformation and repository wiring a real definition would demand.
SUBSCRIBER_KIND = TestKind.TAG


def query_report(query: str, branch: Branch) -> GraphQLQueryReport:
    return InfrahubGraphQLQueryAnalyzer(
        query=query, branch=branch, schema_branch=registry.schema.get_schema_branch(name=branch.name)
    ).query_report
