from graphql import OperationType

from infrahub.auth import AccountSession
from infrahub.exceptions import PermissionDeniedError
from infrahub.graphql.analyzer import GraphQLQueryAnalyzer

from .interface import GraphQLQueryPermissionCheckerInterface


class ReadOnlyGraphQLPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    allowed_readonly_mutations = ["CoreAccountSelfUpdate"]

    async def supports(self, account_session: AccountSession) -> bool:
        return account_session.authenticated and account_session.read_only

    async def check(self, analyzed_query: GraphQLQueryAnalyzer):
        for operation in analyzed_query.operations:
            if (
                operation.operation_type == OperationType.MUTATION
                and operation.name not in self.allowed_readonly_mutations
            ):
                raise PermissionDeniedError("The current account is not authorized to perform this operation")
