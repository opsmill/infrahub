from unittest.mock import AsyncMock, MagicMock

import pytest

from infrahub.auth import AccountSession, AuthType
from infrahub.core.branch import Branch
from infrahub.core.constants import AccountRole
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import AuthorizationError
from infrahub.graphql import GraphqlParams
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.auth.query_permission_checker.default_checker import DefaultGraphQLPermissionChecker


class TestDefaultAuthChecker:
    def setup_method(self):
        self.account_session = AccountSession(account_id="abc", auth_type=AuthType.JWT)
        self.graphql_query = AsyncMock(spec=InfrahubGraphQLQueryAnalyzer)
        self.checker = DefaultGraphQLPermissionChecker()

    @pytest.mark.parametrize("role", [x.value for x in AccountRole])
    async def test_supports_all_accounts(self, db: InfrahubDatabase, branch: Branch, role):
        self.account_session.role = role

        is_supported = await self.checker.supports(db=db, account_session=self.account_session, branch=branch)

        assert is_supported is True

    async def test_always_raises_error(self, db: InfrahubDatabase, branch: Branch):
        with pytest.raises(AuthorizationError):
            await self.checker.check(
                db=db,
                account_session=self.account_session,
                analyzed_query=self.graphql_query,
                query_parameters=MagicMock(spec=GraphqlParams),
                branch=branch,
            )
