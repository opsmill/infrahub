from typing import Callable

from infrahub.auth import AccountSession
from infrahub.exceptions import AuthorizationError
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer

from .interface import GraphQLQueryPermissionCheckerInterface


class AnonymousGraphQLPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    def __init__(self, anonymous_access_allowed_func: Callable[[], bool]):
        self.anonymous_access_allowed_func = anonymous_access_allowed_func

    async def supports(self, account_session: AccountSession) -> bool:
        return not account_session.authenticated

    async def check(self, analyzed_query: InfrahubGraphQLQueryAnalyzer):
        if self.anonymous_access_allowed_func() and not analyzed_query.contains_mutation:
            return
        raise AuthorizationError("Authentication is required to perform this operation")
