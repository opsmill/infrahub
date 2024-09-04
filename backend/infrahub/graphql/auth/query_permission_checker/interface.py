from abc import ABC, abstractmethod
from enum import Enum

from infrahub.auth import AccountSession
from infrahub.graphql import GraphqlParams
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer


class CheckerResolution(Enum):
    TERMINATE = 0
    NEXT_CHECKER = 1


class GraphQLQueryPermissionCheckerInterface(ABC):
    @abstractmethod
    async def supports(self, account_session: AccountSession) -> bool: ...

    @abstractmethod
    async def check(
        self, analyzed_query: InfrahubGraphQLQueryAnalyzer, query_parameters: GraphqlParams
    ) -> CheckerResolution: ...
