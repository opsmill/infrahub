from infrahub.auth import AccountSession
from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase
from infrahub.graphql import GraphqlParams
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer

from .interface import CheckerResolution, GraphQLQueryPermissionCheckerInterface


class ReadWriteGraphQLPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    async def supports(
        self, db: InfrahubDatabase, account_session: AccountSession, branch: Branch | str | None = None
    ) -> bool:
        return account_session.authenticated and not account_session.read_only

    async def check(
        self,
        db: InfrahubDatabase,
        analyzed_query: InfrahubGraphQLQueryAnalyzer,
        query_parameters: GraphqlParams,
        branch: Branch | str | None = None,
    ) -> CheckerResolution:
        return CheckerResolution.TERMINATE
