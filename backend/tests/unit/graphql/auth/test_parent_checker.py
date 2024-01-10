from unittest.mock import AsyncMock

import pytest
from infrahub_sdk.analyzer import GraphQLQueryAnalyzer

from infrahub.auth import AccountSession, AuthType
from infrahub.core.constants import AccountRole
from infrahub.exceptions import PermissionDeniedError
from infrahub.graphql.auth.query_permission_checker.checker import GraphQLQueryPermissionChecker
from infrahub.graphql.auth.query_permission_checker.interface import GraphQLQueryPermissionCheckerInterface


class TestParentAuthChecker:
    def setup_method(self):
        self.account_session = AccountSession(account_id="abc", auth_type=AuthType.JWT, role=AccountRole.ADMIN)
        self.graphql_query = AsyncMock(spec=GraphQLQueryAnalyzer)
        self.sub_auth_checker_one = AsyncMock(spec=GraphQLQueryPermissionCheckerInterface)
        self.sub_auth_checker_two = AsyncMock(spec=GraphQLQueryPermissionCheckerInterface)
        self.sub_auth_checker_one.supports.return_value = False
        self.sub_auth_checker_two.supports.return_value = True
        self.parent_checker = GraphQLQueryPermissionChecker([self.sub_auth_checker_one, self.sub_auth_checker_two])

    async def __call_system_under_test(self):
        await self.parent_checker.check(self.account_session, self.graphql_query)

    async def test_only_checks_one(self):
        await self.__call_system_under_test()

        self.sub_auth_checker_one.supports.assert_awaited_once_with(self.account_session)
        self.sub_auth_checker_two.supports.assert_awaited_once_with(self.account_session)
        self.sub_auth_checker_one.check.assert_not_awaited()
        self.sub_auth_checker_two.check.assert_awaited_once_with(self.graphql_query)

    async def test_error_if_no_support(self):
        self.sub_auth_checker_two.supports.return_value = False

        with pytest.raises(PermissionDeniedError):
            await self.__call_system_under_test()

        self.sub_auth_checker_one.check.assert_not_awaited()
        self.sub_auth_checker_two.check.assert_not_awaited()
