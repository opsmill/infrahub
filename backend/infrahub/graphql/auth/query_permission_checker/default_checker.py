from graphql import OperationType

from infrahub import config
from infrahub.auth import AccountSession
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
        if account_session.permissions:
            self.can_edit_default_branch = "edit_default_branch" in account_session.permissions
        return account_session.authenticated

    async def check(self, analyzed_query: InfrahubGraphQLQueryAnalyzer) -> None:
        for operation in analyzed_query.operations:
            if (
                not self.can_edit_default_branch
                and analyzed_query.branch.name == config.SETTINGS.initial.default_branch
                and operation.operation_type == OperationType.MUTATION
            ):
                raise PermissionDeniedError(
                    f"You are not allowed to change data in the default branch '{config.SETTINGS.initial.default_branch}'"
                )
