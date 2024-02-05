from infrahub.auth import AccountSession
from infrahub.exceptions import AuthorizationError
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer

from .interface import GraphQLQueryPermissionCheckerInterface


class DefaultGraphQLPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    async def supports(self, account_session: AccountSession) -> bool:
        return True

    async def check(self, analyzed_query: InfrahubGraphQLQueryAnalyzer) -> None:
        raise AuthorizationError("Authentication is required to perform this operation")
