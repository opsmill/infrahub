from infrahub.auth import AccountSession
from infrahub.core import registry
from infrahub.core.account import GlobalPermission
from infrahub.core.branch import Branch
from infrahub.core.constants import GlobalPermissions, PermissionDecision
from infrahub.database import InfrahubDatabase
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.initialization import GraphqlParams

from .interface import CheckerResolution, GraphQLQueryPermissionCheckerInterface


class SuperAdminPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    """Checker allows a user to do anything (if the checker runs first)."""

    permission_required = GlobalPermission(
        id="", name="", action=GlobalPermissions.SUPER_ADMIN.value, decision=PermissionDecision.ALLOW_ALL.value
    )

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
                db=db, account_session=account_session, permission=self.permission_required, branch=branch
            ):
                return CheckerResolution.TERMINATE

        return CheckerResolution.NEXT_CHECKER
