from typing import Callable

from infrahub.auth import AccountSession
from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import AuthorizationError
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.initialization import GraphqlParams

from .interface import CheckerResolution, GraphQLQueryPermissionCheckerInterface


class AnonymousGraphQLPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    def __init__(self, anonymous_access_allowed_func: Callable[[], bool]) -> None:
        self.anonymous_access_allowed_func = anonymous_access_allowed_func

    async def supports(self, db: InfrahubDatabase, account_session: AccountSession, branch: Branch) -> bool:  # noqa: ARG002
        return not account_session.authenticated

    async def check(
        self,
        db: InfrahubDatabase,  # noqa: ARG002
        account_session: AccountSession,  # noqa: ARG002
        analyzed_query: InfrahubGraphQLQueryAnalyzer,
        query_parameters: GraphqlParams,  # noqa: ARG002
        branch: Branch,  # noqa: ARG002
    ) -> CheckerResolution:
        if not self.anonymous_access_allowed_func() or analyzed_query.contains_mutation:
            raise AuthorizationError("Authentication is required to perform this operation")
        return CheckerResolution.NEXT_CHECKER
