from infrahub.auth import AccountSession
from infrahub.exceptions import PermissionDeniedError
from infrahub.graphql.analyzer import GraphQLQueryAnalyzer

from .interface import GraphQLQueryPermissionCheckerInterface


class ReadOnlyGraphQLPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    allowed_readonly_mutations = ["CoreAccountPasswordUpdate"]

    async def supports(self, account_session: AccountSession) -> bool:
        return account_session.authenticated and account_session.read_only

    async def check(self, analyzed_query: GraphQLQueryAnalyzer):
        if not analyzed_query.contains_mutation:
            return
        # TODO: check analyzed query mutation operation name
        raise PermissionDeniedError("The current account is not authorized to perform this operation")
