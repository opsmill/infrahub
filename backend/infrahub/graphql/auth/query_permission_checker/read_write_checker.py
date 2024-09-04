from infrahub.auth import AccountSession
from infrahub.graphql import GraphqlParams
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer

from .interface import CheckerResolution, GraphQLQueryPermissionCheckerInterface


class ReadWriteGraphQLPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    async def supports(self, account_session: AccountSession) -> bool:
        return account_session.authenticated and not account_session.read_only

    async def check(
        self, analyzed_query: InfrahubGraphQLQueryAnalyzer, query_parameters: GraphqlParams
    ) -> CheckerResolution:
        return CheckerResolution.TERMINATE
