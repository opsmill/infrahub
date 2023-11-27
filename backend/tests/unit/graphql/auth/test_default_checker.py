from unittest.mock import AsyncMock

import pytest

from infrahub.auth import AccountSession, AuthType
from infrahub.core.constants import AccountRole
from infrahub.exceptions import AuthorizationError
from infrahub.graphql.analyzer import GraphQLQueryAnalyzer
from infrahub.graphql.auth.query_permission_checker.default_checker import DefaultGraphQLPermissionChecker


class TestDefaultAuthChecker:
    def setup_method(self):
        self.account_session = AccountSession(account_id="abc", auth_type=AuthType.JWT)
        self.graphql_query = AsyncMock(spec=GraphQLQueryAnalyzer)
        self.checker = DefaultGraphQLPermissionChecker()

    @pytest.mark.parametrize("role", [x.value for x in AccountRole])
    async def test_supports_all_accounts(self, role):
        self.account_session.role = role

        is_supported = await self.checker.supports(self.account_session)

        assert is_supported is True

    async def test_always_raises_error(self):
        with pytest.raises(AuthorizationError):
            await self.checker.check(self.graphql_query)
