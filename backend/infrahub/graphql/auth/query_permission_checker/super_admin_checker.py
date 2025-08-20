from infrahub import config
from infrahub.auth import AccountSession
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
        action=GlobalPermissions.SUPER_ADMIN.value, decision=PermissionDecision.ALLOW_ALL.value
    )

    async def supports(self, db: InfrahubDatabase, account_session: AccountSession, branch: Branch) -> bool:  # noqa: ARG002
        return config.SETTINGS.main.allow_anonymous_access or account_session.authenticated

    async def check(
        self,
        db: InfrahubDatabase,  # noqa: ARG002
        account_session: AccountSession,  # noqa: ARG002
        analyzed_query: InfrahubGraphQLQueryAnalyzer,  # noqa: ARG002
        query_parameters: GraphqlParams,
        branch: Branch,  # noqa: ARG002
    ) -> CheckerResolution:
        return (
            CheckerResolution.TERMINATE
            if query_parameters.context.active_permissions.has_permission(permission=self.permission_required)
            else CheckerResolution.NEXT_CHECKER
        )
