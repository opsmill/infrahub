from graphql import OperationType

from infrahub import config
from infrahub.auth import AccountSession
from infrahub.core.constants import GLOBAL_BRANCH_NAME, GlobalPermissions
from infrahub.exceptions import AuthorizationError, PermissionDeniedError
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer

from .interface import GraphQLQueryPermissionCheckerInterface


class DefaultGraphQLPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    async def supports(self, account_session: AccountSession) -> bool:
        return True

    async def check(self, analyzed_query: InfrahubGraphQLQueryAnalyzer) -> None:
        raise AuthorizationError("Authentication is required to perform this operation")


class DefaultBranchPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    def __init__(self) -> None:
        self.can_edit_default_branch: bool = False

    async def supports(self, account_session: AccountSession) -> bool:
        if account_session.permissions is not None and (
            global_permissions := account_session.permissions.get("global_permissions", [])
        ):
            self.can_edit_default_branch = GlobalPermissions.EDIT_DEFAULT_BRANCH.value in global_permissions
        return account_session.authenticated

    async def check(self, analyzed_query: InfrahubGraphQLQueryAnalyzer) -> None:
        for operation in analyzed_query.operations:
            if (
                not self.can_edit_default_branch
                and (
                    analyzed_query.branch is None
                    or analyzed_query.branch.name in (GLOBAL_BRANCH_NAME, config.SETTINGS.initial.default_branch)
                )
                and operation.operation_type == OperationType.MUTATION
            ):
                raise PermissionDeniedError(
                    f"You are not allowed to change data in the default branch '{config.SETTINGS.initial.default_branch}'"
                )
