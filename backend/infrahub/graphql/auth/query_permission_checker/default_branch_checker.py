from infrahub import config
from infrahub.auth import AccountSession
from infrahub.core import registry
from infrahub.core.account import GlobalPermission
from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME, GlobalPermissions, PermissionDecision
from infrahub.database import InfrahubDatabase
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.initialization import GraphqlParams

from .interface import CheckerResolution, GraphQLQueryPermissionCheckerInterface


class DefaultBranchPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    """Checker that makes sure a user account can edit data in the default branch."""

    permission_required = GlobalPermission(
        action=GlobalPermissions.EDIT_DEFAULT_BRANCH.value, decision=PermissionDecision.ALLOW_ALL.value
    )
    exempt_operations = [
        "BranchCreate",
        "DiffUpdate",
        "InfrahubAccountSelfUpdate",
        "InfrahubAccountTokenCreate",
        "InfrahubAccountTokenDelete",
    ]

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
        operates_on_default_branch = analyzed_query.branch is None or analyzed_query.branch.name in (
            GLOBAL_BRANCH_NAME,
            registry.default_branch,
        )
        is_exempt_operation = all(
            operation_name in self.exempt_operations for operation_name in analyzed_query.operation_names
        )

        if operates_on_default_branch and analyzed_query.contains_mutation and not is_exempt_operation:
            query_parameters.context.active_permissions.raise_for_permission(permission=self.permission_required)

        return CheckerResolution.NEXT_CHECKER
