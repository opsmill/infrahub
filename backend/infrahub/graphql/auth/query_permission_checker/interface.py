from abc import ABC, abstractmethod
from enum import Enum

from infrahub.auth import AccountSession
from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.initialization import GraphqlParams


class CheckerResolution(Enum):
    TERMINATE = 0
    NEXT_CHECKER = 1


class GraphQLQueryPermissionCheckerInterface(ABC):
    @abstractmethod
    async def supports(self, db: InfrahubDatabase, account_session: AccountSession, branch: Branch) -> bool: ...

    @abstractmethod
    async def check(
        self,
        db: InfrahubDatabase,
        account_session: AccountSession,
        analyzed_query: InfrahubGraphQLQueryAnalyzer,
        query_parameters: GraphqlParams,
        branch: Branch,
    ) -> CheckerResolution: ...
