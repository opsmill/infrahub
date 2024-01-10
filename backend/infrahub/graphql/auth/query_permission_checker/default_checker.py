from infrahub_sdk.analyzer import GraphQLQueryAnalyzer

from infrahub.auth import AccountSession
from infrahub.exceptions import AuthorizationError

from .interface import GraphQLQueryPermissionCheckerInterface


class DefaultGraphQLPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    async def supports(self, account_session: AccountSession) -> bool:
        return True

    async def check(self, analyzed_query: GraphQLQueryAnalyzer):
        raise AuthorizationError("Authentication is required to perform this operation")
