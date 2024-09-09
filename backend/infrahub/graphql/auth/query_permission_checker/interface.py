from abc import ABC, abstractmethod
from enum import Enum

from infrahub.auth import AccountSession
from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase
from infrahub.graphql import GraphqlParams
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer


class CheckerResolution(Enum):
    TERMINATE = 0
    NEXT_CHECKER = 1


class GraphQLQueryPermissionCheckerInterface(ABC):
    @abstractmethod
    async def supports(
        self, db: InfrahubDatabase, account_session: AccountSession, branch: Branch | str | None = None
    ) -> bool: ...

    @abstractmethod
    async def check(
        self,
        db: InfrahubDatabase,
        analyzed_query: InfrahubGraphQLQueryAnalyzer,
        query_parameters: GraphqlParams,
        branch: Branch | str | None = None,
    ) -> CheckerResolution: ...
