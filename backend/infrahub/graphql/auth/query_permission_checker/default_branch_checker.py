from infrahub import config
from infrahub.auth import AccountSession
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import PermissionDeniedError
from infrahub.graphql import GraphqlParams
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer

from .interface import CheckerResolution, GraphQLQueryPermissionCheckerInterface


class DefaultBranchPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    permission_required = "global:edit_default_branch:allow"
    exempt_operations = ["BranchCreate"]

    def __init__(self) -> None:
        self.can_edit_default_branch: bool = False

    async def supports(
        self, db: InfrahubDatabase, account_session: AccountSession, branch: Branch | str | None = None
    ) -> bool:
        self.can_edit_default_branch = False

        if registry.permission_backends and account_session.authenticated:
            for permission_backend in registry.permission_backends:
                self.can_edit_default_branch = await permission_backend.has_permission(
                    db=db, account_id=account_session.account_id, permission=self.permission_required, branch=branch
                )
                if self.can_edit_default_branch:
                    break

        return account_session.authenticated

    async def check(
        self,
        db: InfrahubDatabase,
        analyzed_query: InfrahubGraphQLQueryAnalyzer,
        query_parameters: GraphqlParams,
        branch: Branch | str | None = None,
    ) -> CheckerResolution:
        operates_on_default_branch = analyzed_query.branch is None or analyzed_query.branch.name in (
            GLOBAL_BRANCH_NAME,
            config.SETTINGS.initial.default_branch,
        )
        is_exempt_operation = analyzed_query.operation_name is not None and (
            analyzed_query.operation_name in self.exempt_operations
            or analyzed_query.operation_name.startswith("InfrahubAccount")  # Allow user to manage self
        )

        if (
            not self.can_edit_default_branch
            and operates_on_default_branch
            and analyzed_query.contains_mutation
            and not is_exempt_operation
        ):
            raise PermissionDeniedError(
                f"You are not allowed to change data in the default branch '{config.SETTINGS.initial.default_branch}'"
            )

        return CheckerResolution.NEXT_CHECKER
