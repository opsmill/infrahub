from infrahub.auth import AccountSession
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME, GlobalPermissions, PermissionDecision
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry
from infrahub.exceptions import PermissionDeniedError
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.initialization import GraphqlParams
from infrahub.permissions.manager import PermissionManager

from .interface import CheckerResolution, GraphQLQueryPermissionCheckerInterface


class DefaultBranchPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    """Checker that makes sure a user account can edit data in the default branch."""

    permission_required = f"global:{GlobalPermissions.EDIT_DEFAULT_BRANCH.value}:{PermissionDecision.ALLOW.value}"
    exempt_operations = ["BranchCreate"]

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

        can_edit_default_branch = await permission_manager.has_permission(
            account_session=account_session, permission=self.permission_required
        )
        operates_on_default_branch = analyzed_query.branch is None or analyzed_query.branch.name in (
            GLOBAL_BRANCH_NAME,
            registry.default_branch,
        )
        is_exempt_operation = analyzed_query.operation_name is not None and (
            analyzed_query.operation_name in self.exempt_operations
            or analyzed_query.operation_name.startswith("InfrahubAccount")  # Allow user to manage self
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
