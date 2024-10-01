from unittest.mock import AsyncMock, MagicMock

import pytest

from infrahub.auth import AccountSession, AuthType
from infrahub.core.branch import Branch
from infrahub.core.constants import AccountRole
from infrahub.database import InfrahubDatabase
from infrahub.graphql import GraphqlParams
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.auth.query_permission_checker.read_write_checker import ReadWriteGraphQLPermissionChecker


class TestReadWriteAuthChecker:
    def setup_method(self):
        self.account_session = AccountSession(account_id="abc", auth_type=AuthType.JWT, role=AccountRole.ADMIN)
        self.graphql_query = AsyncMock(spec=InfrahubGraphQLQueryAnalyzer)
        self.checker = ReadWriteGraphQLPermissionChecker()

    @pytest.mark.parametrize("role", [AccountRole.ADMIN, AccountRole.READ_WRITE])
    async def test_supports_readwrite_accounts(self, db: InfrahubDatabase, branch: Branch, role):
        self.account_session.role = role

        is_supported = await self.checker.supports(db=db, account_session=self.account_session, branch=branch)

        assert is_supported is True

    async def test_doesnt_support_readonly_accounts(self, db: InfrahubDatabase, branch: Branch):
        self.account_session.role = AccountRole.READ_ONLY

        is_supported = await self.checker.supports(db=db, account_session=self.account_session, branch=branch)

        assert is_supported is False

    @pytest.mark.parametrize("contains_mutations", [True, False])
    async def test_never_raises_error(self, db: InfrahubDatabase, branch: Branch, contains_mutations):
        self.graphql_query.contains_mutations = contains_mutations

        await self.checker.check(
            db=db,
            account_session=self.account_session,
            analyzed_query=self.graphql_query,
            query_parameters=MagicMock(spec=GraphqlParams),
            branch=branch,
        )
