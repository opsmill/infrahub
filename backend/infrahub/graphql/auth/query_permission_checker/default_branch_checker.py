from infrahub import config
from infrahub.auth import AccountSession
from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.exceptions import PermissionDeniedError
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer

from .interface import GraphQLQueryPermissionCheckerInterface


class DefaultBranchPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    permissions_required = ["global:edit_default_branch:allow"]

    def __init__(self) -> None:
        self.can_edit_default_branch: bool = False

    async def supports(self, account_session: AccountSession) -> bool:
        self.can_edit_default_branch = (
            account_session.permissions is not None
            and account_session.permissions.has_permissions(self.permissions_required)
        )
        return account_session.authenticated

    async def check(self, analyzed_query: InfrahubGraphQLQueryAnalyzer) -> None:
        if (
            not self.can_edit_default_branch
            and (
                analyzed_query.branch is None
                or analyzed_query.branch.name in (GLOBAL_BRANCH_NAME, config.SETTINGS.initial.default_branch)
            )
            and analyzed_query.contains_mutation
            and analyzed_query.operation_name != "BranchCreate"  # Find a way better way to reference this?
        ):
            raise PermissionDeniedError(
                f"You are not allowed to change data in the default branch '{config.SETTINGS.initial.default_branch}'"
            )
