from typing import Optional

from infrahub.auth import AccountPermissions, AccountSession

# from infrahub.core.constants import PermissionAction
# from infrahub.exceptions import PermissionDeniedError
from infrahub.graphql import GraphqlParams
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer

from .interface import CheckerResolution, GraphQLQueryPermissionCheckerInterface


class ObjectPermissionChecker(GraphQLQueryPermissionCheckerInterface):
    def __init__(self) -> None:
        self.permissions: Optional[AccountPermissions] = None

    async def supports(self, account_session: AccountSession) -> bool:
        self.permissions = account_session.permissions
        return account_session.authenticated

    async def check(
        self, analyzed_query: InfrahubGraphQLQueryAnalyzer, query_parameters: GraphqlParams
    ) -> CheckerResolution:
        # kinds = await analyzed_query.get_models_in_use(types=query_parameters.context.types)

        # if not self.permissions.has_object_permissions(kinds=kinds):
        #    raise PermissionDeniedError(f"You are not allowed to perform $$SOMETHING$$ on {kinds}")

        return CheckerResolution.NEXT_CHECKER
