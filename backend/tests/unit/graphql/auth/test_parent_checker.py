from unittest.mock import AsyncMock, MagicMock

import pytest

from infrahub.auth import AccountSession, AuthType
from infrahub.core.branch import Branch
from infrahub.core.constants import AccountRole
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import PermissionDeniedError
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.auth.query_permission_checker.checker import GraphQLQueryPermissionChecker
from infrahub.graphql.auth.query_permission_checker.interface import (
    CheckerResolution,
    GraphQLQueryPermissionCheckerInterface,
)
from infrahub.graphql.initialization import GraphqlParams


class TestParentAuthChecker:
    def setup_method(self):
        self.account_session = AccountSession(account_id="abc", auth_type=AuthType.JWT, role=AccountRole.ADMIN)
        self.graphql_query = AsyncMock(spec=InfrahubGraphQLQueryAnalyzer)
        self.query_parameters = MagicMock(spec=GraphqlParams)
        self.sub_auth_checker_one = AsyncMock(spec=GraphQLQueryPermissionCheckerInterface)
        self.sub_auth_checker_two = AsyncMock(spec=GraphQLQueryPermissionCheckerInterface)
        self.sub_auth_checker_one.supports.return_value = False
        self.sub_auth_checker_two.supports.return_value = True
        self.sub_auth_checker_one.check = AsyncMock()
        self.sub_auth_checker_one.check.return_value = CheckerResolution.TERMINATE
        self.sub_auth_checker_two.check = AsyncMock()
        self.sub_auth_checker_two.check.return_value = CheckerResolution.TERMINATE
        self.parent_checker = GraphQLQueryPermissionChecker([self.sub_auth_checker_one, self.sub_auth_checker_two])

    async def __call_system_under_test(self, db: InfrahubDatabase, branch: Branch):
        await self.parent_checker.check(
            db=db,
            account_session=self.account_session,
            analyzed_query=self.graphql_query,
            query_parameters=self.query_parameters,
            branch=branch,
        )

    async def test_only_checks_one(self, db: InfrahubDatabase, branch: Branch):
        await self.__call_system_under_test(db=db, branch=branch)

        self.sub_auth_checker_one.supports.assert_awaited_once_with(
            db=db, account_session=self.account_session, branch=branch
        )
        self.sub_auth_checker_two.supports.assert_awaited_once_with(
            db=db, account_session=self.account_session, branch=branch
        )
        self.sub_auth_checker_one.check.assert_not_awaited()
        self.sub_auth_checker_two.check.assert_awaited_once_with(
            db=db,
            account_session=self.account_session,
            analyzed_query=self.graphql_query,
            query_parameters=self.query_parameters,
            branch=branch,
        )

    async def test_error_if_no_support(self, db: InfrahubDatabase, branch: Branch):
        self.sub_auth_checker_two.supports.return_value = False

        with pytest.raises(PermissionDeniedError):
            await self.__call_system_under_test(db=db, branch=branch)

        self.sub_auth_checker_one.check.assert_not_awaited()
        self.sub_auth_checker_two.check.assert_not_awaited()
