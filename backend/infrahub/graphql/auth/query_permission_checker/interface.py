from abc import ABC, abstractmethod

from infrahub_sdk.analyzer import GraphQLQueryAnalyzer

from infrahub.auth import AccountSession


class GraphQLQueryPermissionCheckerInterface(ABC):
    @abstractmethod
    async def supports(self, account_session: AccountSession) -> bool:
        ...

    @abstractmethod
    async def check(self, analyzed_query: GraphQLQueryAnalyzer):
        ...
