from graphql import OperationType

from infrahub.auth import AccountSession
from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import PermissionDeniedError
from infrahub.graphql import GraphqlParams
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer

from .interface import CheckerResolution, GraphQLQueryPermissionCheckerInterface


class ReadOnlyGraphQLPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    allowed_readonly_mutations = ["InfrahubAccountSelfUpdate"]

    async def supports(
        self, db: InfrahubDatabase, account_session: AccountSession, branch: Branch | str | None = None
    ) -> bool:
        return account_session.authenticated and account_session.read_only

    async def check(
        self,
        db: InfrahubDatabase,
        analyzed_query: InfrahubGraphQLQueryAnalyzer,
        query_parameters: GraphqlParams,
        branch: Branch | str | None = None,
    ) -> CheckerResolution:
        for operation in analyzed_query.operations:
            if (
                operation.operation_type == OperationType.MUTATION
                and operation.name not in self.allowed_readonly_mutations
            ):
                raise PermissionDeniedError("The current account is not authorized to perform this operation")

        return CheckerResolution.TERMINATE
