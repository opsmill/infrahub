from infrahub.auth import AccountSession
from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import PermissionDeniedError
from infrahub.graphql import GraphqlParams
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer

from .interface import CheckerResolution, GraphQLQueryPermissionCheckerInterface


class GraphQLQueryPermissionChecker:
    def __init__(self, sub_checkers: list[GraphQLQueryPermissionCheckerInterface]):
        self.sub_checkers = sub_checkers

    async def check(
        self,
        db: InfrahubDatabase,
        account_session: AccountSession,
        analyzed_query: InfrahubGraphQLQueryAnalyzer,
        query_parameters: GraphqlParams,
        branch: Branch | str | None = None,
    ) -> None:
        for sub_checker in self.sub_checkers:
            if await sub_checker.supports(db=db, account_session=account_session, branch=branch):
                resolution = await sub_checker.check(
                    db=db, analyzed_query=analyzed_query, query_parameters=query_parameters, branch=branch
                )
                if resolution == CheckerResolution.TERMINATE:
                    return
        raise PermissionDeniedError("The current account is not authorized to perform this operation")
