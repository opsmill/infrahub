from typing import List

from infrahub_sdk.analyzer import GraphQLQueryAnalyzer

from infrahub.auth import AccountSession
from infrahub.exceptions import PermissionDeniedError

from .interface import GraphQLQueryPermissionCheckerInterface


class GraphQLQueryPermissionChecker:
    def __init__(self, sub_checkers: List[GraphQLQueryPermissionCheckerInterface]):
        self.sub_checkers = sub_checkers

    async def check(self, account_session: AccountSession, analyzed_query: GraphQLQueryAnalyzer):
        for sub_checker in self.sub_checkers:
            if await sub_checker.supports(account_session):
                await sub_checker.check(analyzed_query)
                return
        raise PermissionDeniedError("The current account is not authorized to perform this operation")
