from infrahub.auth import AccountSession
from infrahub.core import registry
from infrahub.core.account import GlobalPermission
from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME, GlobalPermissions, PermissionDecision
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import PermissionDeniedError
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.initialization import GraphqlParams

from .interface import CheckerResolution, GraphQLQueryPermissionCheckerInterface


class DefaultBranchPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    """Checker that makes sure a user account can edit data in the default branch."""

    permission_required = GlobalPermission(
        id="", name="", action=GlobalPermissions.EDIT_DEFAULT_BRANCH.value, decision=PermissionDecision.ALLOW_ALL.value
    )
    exempt_operations = [
        "BranchCreate",
        "DiffUpdate",
        "InfrahubAccountSelfUpdate",
        "InfrahubAccountTokenCreate",
        "InfrahubAccountTokenDelete",
    ]

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
        can_edit_default_branch = False
        for permission_backend in registry.permission_backends:
            can_edit_default_branch = await permission_backend.has_permission(
                db=db, account_session=account_session, permission=self.permission_required, branch=branch
            )
            if can_edit_default_branch:
                break

        operates_on_default_branch = analyzed_query.branch is None or analyzed_query.branch.name in (
            GLOBAL_BRANCH_NAME,
            registry.default_branch,
        )
        is_exempt_operation = all(
            operation_name in self.exempt_operations for operation_name in analyzed_query.operation_names
        )

        if (
            not can_edit_default_branch
            and operates_on_default_branch
            and analyzed_query.contains_mutation
            and not is_exempt_operation
        ):
            raise PermissionDeniedError(
                f"You are not allowed to change data in the default branch '{registry.default_branch}'"
            )

        return CheckerResolution.NEXT_CHECKER
