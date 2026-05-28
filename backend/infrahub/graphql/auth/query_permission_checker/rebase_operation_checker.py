from infrahub import config
from infrahub.auth.session import AccountSession
from infrahub.core.account import GlobalPermission
from infrahub.core.branch import Branch
from infrahub.core.constants import GlobalPermissions, PermissionDecision
from infrahub.database import InfrahubDatabase
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.initialization import GraphqlParams

from .interface import CheckerResolution, GraphQLQueryPermissionCheckerInterface


class RebaseBranchPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    """Checker that makes sure a user account can rebase a branch."""

    permission_required = GlobalPermission(
        action=GlobalPermissions.REBASE_BRANCH.value, decision=PermissionDecision.ALLOW_ALL.value
    )

    async def supports(self, db: InfrahubDatabase, account_session: AccountSession, branch: Branch) -> bool:  # noqa: ARG002
        return config.SETTINGS.main.allow_anonymous_access or account_session.authenticated

    async def check(
        self,
        db: InfrahubDatabase,  # noqa: ARG002
        account_session: AccountSession,  # noqa: ARG002
        analyzed_query: InfrahubGraphQLQueryAnalyzer,
        query_parameters: GraphqlParams,
        branch: Branch,  # noqa: ARG002
    ) -> CheckerResolution:
        if "BranchRebase" in [operation.name for operation in analyzed_query.operations]:
            query_parameters.context.active_permissions.raise_for_permission(permission=self.permission_required)
            return CheckerResolution.TERMINATE

        return CheckerResolution.NEXT_CHECKER
