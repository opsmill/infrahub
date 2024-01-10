from unittest.mock import AsyncMock

import pytest

from infrahub.auth import AccountSession, AuthType
from infrahub.core.constants import AccountRole
from infrahub.graphql.analyzer import GraphQLQueryAnalyzer
from infrahub.graphql.auth.query_permission_checker.read_write_checker import ReadWriteGraphQLPermissionChecker


class TestReadWriteAuthChecker:
    def setup_method(self):
        self.account_session = AccountSession(account_id="abc", auth_type=AuthType.JWT, role=AccountRole.ADMIN)
        self.graphql_query = AsyncMock(spec=GraphQLQueryAnalyzer)
        self.checker = ReadWriteGraphQLPermissionChecker()

    @pytest.mark.parametrize("role", [AccountRole.ADMIN, AccountRole.READ_WRITE])
    async def test_supports_readwrite_accounts(self, role):
        self.account_session.role = role

        is_supported = await self.checker.supports(self.account_session)

        assert is_supported is True

    async def test_doesnt_support_readonly_accounts(self):
        self.account_session.role = AccountRole.READ_ONLY

        is_supported = await self.checker.supports(self.account_session)

        assert is_supported is False

    @pytest.mark.parametrize("contains_mutations", [True, False])
    async def test_never_raises_error(self, contains_mutations):
        self.graphql_query.contains_mutations = contains_mutations

        await self.checker.check(self.graphql_query)
