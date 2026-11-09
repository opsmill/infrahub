from typing import Callable

from infrahub.auth.session import AccountSession
from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import AuthorizationError
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.initialization import GraphqlParams

from .interface import CheckerResolution, GraphQLQueryPermissionCheckerInterface


class AnonymousGraphQLPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    def __init__(
        self,
        anonymous_access_allowed_func: Callable[[], bool],
        operations_requiring_authentication: frozenset[str],
    ) -> None:
        self.anonymous_access_allowed_func = anonymous_access_allowed_func
        # Top-level operation names an anonymous session may never run, even when anonymous read
        # access is enabled: they resolve data bound to the caller's identity.
        self.operations_requiring_authentication = operations_requiring_authentication

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
        if (
            not self.anonymous_access_allowed_func()
            or analyzed_query.contains_mutation
            or self.operations_requiring_authentication.intersection(analyzed_query.operation_names)
        ):
            raise AuthorizationError("Authentication is required to perform this operation")
        return CheckerResolution.NEXT_CHECKER
