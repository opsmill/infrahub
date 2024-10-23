from infrahub.auth import AccountSession
from infrahub.core import registry
from infrahub.core.account import GlobalPermission
from infrahub.core.branch import Branch
from infrahub.core.constants import GlobalPermissions, PermissionDecision
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import PermissionDeniedError
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.initialization import GraphqlParams

from .interface import CheckerResolution, GraphQLQueryPermissionCheckerInterface


class MergeBranchPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    """Checker that makes sure a user account can merge a branch without going through a proposed change."""

    permission_required = GlobalPermission(
        id="", name="", action=GlobalPermissions.MERGE_BRANCH.value, decision=PermissionDecision.ALLOW_ALL.value
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
        if "BranchMerge" in [operation.name for operation in analyzed_query.operations]:
            can_merge_branch = False
            for permission_backend in registry.permission_backends:
                can_merge_branch = await permission_backend.has_permission(
                    db=db, account_session=account_session, permission=self.permission_required, branch=branch
                )
                if can_merge_branch:
                    break

            if not can_merge_branch:
                raise PermissionDeniedError("You are not allowed to merge a branch")

            return CheckerResolution.TERMINATE

        return CheckerResolution.NEXT_CHECKER
