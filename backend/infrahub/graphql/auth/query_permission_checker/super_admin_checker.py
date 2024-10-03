from infrahub.auth import AccountSession
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import GlobalPermissions
from infrahub.database import InfrahubDatabase
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.initialization import GraphqlParams

from .interface import CheckerResolution, GraphQLQueryPermissionCheckerInterface


class SuperAdminPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    permission_required = f"global:{GlobalPermissions.SUPER_ADMIN.value}:allow"

    async def supports(self, db: InfrahubDatabase, account_session: AccountSession, branch: Branch) -> bool:
        return account_session.authenticated

    async def check(
        self,
        db: InfrahubDatabase,
        account_session: AccountSession,
        analyzed_query: InfrahubGraphQLQueryAnalyzer,
        query_parameters: GraphqlParams,
        branch: Branch,
    ) -> CheckerResolution:
        for permission_backend in registry.permission_backends:
            if await permission_backend.has_permission(
                db=db, account_id=account_session.account_id, permission=self.permission_required, branch=branch
            ):
                return CheckerResolution.TERMINATE

        return CheckerResolution.NEXT_CHECKER
