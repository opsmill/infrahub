from graphql import OperationType

from infrahub.auth import AccountSession
from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import PermissionDeniedError
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.initialization import GraphqlParams

from .interface import CheckerResolution, GraphQLQueryPermissionCheckerInterface


class ReadOnlyGraphQLPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    allowed_readonly_mutations = ["InfrahubAccountSelfUpdate"]

    async def supports(self, db: InfrahubDatabase, account_session: AccountSession, branch: Branch) -> bool:
        return account_session.authenticated and account_session.read_only

    async def check(
        self,
        db: InfrahubDatabase,
        account_session: AccountSession,
        analyzed_query: InfrahubGraphQLQueryAnalyzer,
        query_parameters: GraphqlParams,
        branch: Branch,
    ) -> CheckerResolution:
        for operation in analyzed_query.operations:
            if (
                operation.operation_type == OperationType.MUTATION
                and operation.name not in self.allowed_readonly_mutations
            ):
                raise PermissionDeniedError("The current account is not authorized to perform this operation")

        return CheckerResolution.TERMINATE
