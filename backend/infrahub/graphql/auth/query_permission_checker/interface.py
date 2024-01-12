from abc import ABC, abstractmethod

from infrahub.auth import AccountSession
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer


class GraphQLQueryPermissionCheckerInterface(ABC):
    @abstractmethod
    async def supports(self, account_session: AccountSession) -> bool:
        ...

    @abstractmethod
    async def check(self, analyzed_query: InfrahubGraphQLQueryAnalyzer):
        ...
