from abc import ABC, abstractmethod
from enum import Enum

from infrahub.auth.session import AccountSession
from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.initialization import GraphqlParams


class CheckerResolution(Enum):
    TERMINATE = 0
    NEXT_CHECKER = 1


class GraphQLQueryPermissionCheckerInterface(ABC):
    """Base interface for all permission checkers in the pipeline.

    Pipeline contract:
    - Checkers are called in registration order
    - supports() determines if a checker should run for this request
    - check() performs the actual permission check
    - TERMINATE stops the chain (request is authorized)
    - NEXT_CHECKER continues to the next checker
    - If no checker returns TERMINATE, the request is denied

    Checker categories (by convention):
    - Pre-filter: Rejects unauthenticated requests with AuthorizationError. Runs first in the pipeline.
    - Gate: May short-circuit (TERMINATE) or pass (NEXT_CHECKER). Never raises.
    - Enforcement: Raises PermissionDeniedError if violated, returns NEXT_CHECKER.
    - Terminal: Always returns TERMINATE. Must be last.
    """

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
