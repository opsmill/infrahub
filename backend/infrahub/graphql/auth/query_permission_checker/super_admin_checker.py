from infrahub.auth import AccountSession
from infrahub.core.branch import Branch
from infrahub.core.constants import GlobalPermissions
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.initialization import GraphqlParams
from infrahub.permissions.manager import PermissionManager

from .interface import CheckerResolution, GraphQLQueryPermissionCheckerInterface


class SuperAdminPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    """Checker allows a user to do anything (if the checker runs first)."""

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
        component_registry = get_component_registry()
        permission_manager = component_registry.get_component(PermissionManager, db=db, branch=branch)

        if await permission_manager.has_permission(
            account_session=account_session, permission=self.permission_required
        ):
            return CheckerResolution.TERMINATE

        return CheckerResolution.NEXT_CHECKER
