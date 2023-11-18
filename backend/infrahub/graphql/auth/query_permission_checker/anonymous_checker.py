from infrahub.auth import AccountSession
from infrahub.exceptions import AuthorizationError
from infrahub.graphql.analyzer import GraphQLQueryAnalyzer

from .interface import GraphQLQueryPermissionCheckerInterface


class AnonymousGraphQLPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    def __init__(self, anonymous_access_allowed: bool):
        self.anonymous_access_allowed = anonymous_access_allowed

    async def supports(self, account_session: AccountSession) -> bool:
        return not account_session.authenticated

    async def check(self, analyzed_query: GraphQLQueryAnalyzer):
        if self.anonymous_access_allowed and not analyzed_query.contains_mutation:
            return
        raise AuthorizationError("Authentication is required to perform this operation")
