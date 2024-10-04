from infrahub.auth import AccountSession
from infrahub.core.branch import Branch
from infrahub.core.constants import GlobalPermissions
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry
from infrahub.exceptions import PermissionDeniedError
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.initialization import GraphqlParams
from infrahub.permissions.manager import PermissionManager

from .interface import CheckerResolution, GraphQLQueryPermissionCheckerInterface


class MergeBranchPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    """Checker that makes sure a user account can merge a branch without going through a proposed change."""

    permission_required = f"global:{GlobalPermissions.MERGE_BRANCH.value}:allow"

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

        if "BranchMerge" in [operation.name for operation in analyzed_query.operations]:
            if not await permission_manager.has_permission(
                account_session=account_session, permission=self.permission_required
            ):
                raise PermissionDeniedError("You are not allowed to merge a branch")

            return CheckerResolution.TERMINATE

        return CheckerResolution.NEXT_CHECKER
