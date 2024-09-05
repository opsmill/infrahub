from unittest.mock import AsyncMock, MagicMock

import pytest
from graphql import OperationType
from infrahub_sdk.analyzer import GraphQLOperation

from infrahub.auth import AccountSession, AuthType
from infrahub.core.branch import Branch
from infrahub.core.constants import AccountRole
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import PermissionDeniedError
from infrahub.graphql import GraphqlParams
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.auth.query_permission_checker.read_only_checker import ReadOnlyGraphQLPermissionChecker


class TestReadOnlyAuthChecker:
    def setup_method(self):
        self.account_session = AccountSession(account_id="abc", auth_type=AuthType.JWT, role=AccountRole.READ_ONLY)
        self.graphql_query = AsyncMock(spec=InfrahubGraphQLQueryAnalyzer)
        self.query_parameters = MagicMock(spec=GraphqlParams)
        self.checker = ReadOnlyGraphQLPermissionChecker()

    @pytest.mark.parametrize("role", [AccountRole.ADMIN, AccountRole.READ_WRITE])
    async def test_doesnt_supports_other_accounts(self, db: InfrahubDatabase, branch: Branch, role):
        self.account_session.role = role

        is_supported = await self.checker.supports(db=db, account_session=self.account_session, branch=branch)

        assert is_supported is False

    async def test_supports_read_only_accounts(self, db: InfrahubDatabase, branch: Branch):
        self.account_session.role = AccountRole.READ_ONLY

        is_supported = await self.checker.supports(db=db, account_session=self.account_session, branch=branch)

        assert is_supported is True

    async def test_illegal_mutation_raises_error(self, db: InfrahubDatabase, branch: Branch):
        self.graphql_query.contains_mutation = True
        self.graphql_query.operations = [
            GraphQLOperation(name="ThisIsNotAllowed", operation_type=OperationType.MUTATION)
        ]

        with pytest.raises(PermissionDeniedError):
            await self.checker.check(
                db=db, analyzed_query=self.graphql_query, query_parameters=self.query_parameters, branch=branch
            )

    async def test_legal_mutation_is_okay(self, db: InfrahubDatabase, branch: Branch):
        self.checker.allowed_readonly_mutations = ["ThisIsAllowed"]
        self.graphql_query.contains_mutation = True
        self.graphql_query.operations = [GraphQLOperation(name="ThisIsAllowed", operation_type=OperationType.MUTATION)]

        await self.checker.check(
            db=db, analyzed_query=self.graphql_query, query_parameters=self.query_parameters, branch=branch
        )

    async def test_query_is_okay(self, db: InfrahubDatabase, branch: Branch):
        self.graphql_query.contains_mutation = False
        self.graphql_query.operations = [GraphQLOperation(name="ThisIsAQuery", operation_type=OperationType.QUERY)]

        await self.checker.check(
            db=db, analyzed_query=self.graphql_query, query_parameters=self.query_parameters, branch=branch
        )
