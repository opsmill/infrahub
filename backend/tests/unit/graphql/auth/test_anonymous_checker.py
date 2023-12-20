from unittest.mock import AsyncMock, MagicMock

import pytest

from infrahub.auth import AccountSession, AuthType
from infrahub.exceptions import AuthorizationError
from infrahub.graphql.analyzer import GraphQLQueryAnalyzer
from infrahub.graphql.auth.query_permission_checker.anonymous_checker import AnonymousGraphQLPermissionChecker


class TestAnonymousAuthChecker:
    def setup_method(self):
        self.account_session = AccountSession(account_id="abc", auth_type=AuthType.JWT)
        self.graphql_query = AsyncMock(spec=GraphQLQueryAnalyzer)
        self.mock_anonymous_setting_get = MagicMock(return_value=True)
        self.checker = AnonymousGraphQLPermissionChecker(self.mock_anonymous_setting_get)

    @pytest.mark.parametrize("is_authenticated,is_supported", [(True, False), (False, True)])
    async def test_supports_unauthenticated_accounts(self, is_authenticated, is_supported):
        self.account_session.authenticated = is_authenticated

        has_support = await self.checker.supports(self.account_session)

        assert is_supported is has_support

    @pytest.mark.parametrize("anonymous_setting,query_has_mutations", [(False, False), (False, True), (True, True)])
    async def test_failures_raise_error(self, anonymous_setting, query_has_mutations):
        self.mock_anonymous_setting_get.return_value = anonymous_setting
        self.graphql_query.contains_mutation = query_has_mutations

        with pytest.raises(AuthorizationError):
            await self.checker.check(self.graphql_query)

    async def test_check_passes(self):
        self.mock_anonymous_setting_get.return_value = True
        self.graphql_query.contains_mutation = False

        await self.checker.check(self.graphql_query)
