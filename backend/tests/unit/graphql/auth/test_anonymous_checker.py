from unittest.mock import AsyncMock, MagicMock

import pytest

from infrahub.auth import AccountSession, AuthType
from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import AuthorizationError
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.auth.query_permission_checker.anonymous_checker import AnonymousGraphQLPermissionChecker
from infrahub.graphql.initialization import GraphqlParams


class TestAnonymousAuthChecker:
    def setup_method(self):
        self.account_session = AccountSession(account_id="abc", auth_type=AuthType.JWT)
        self.graphql_query = AsyncMock(spec=InfrahubGraphQLQueryAnalyzer)
        self.query_parameters = MagicMock(spec=GraphqlParams)
        self.mock_anonymous_setting_get = MagicMock(return_value=True)
        self.checker = AnonymousGraphQLPermissionChecker(self.mock_anonymous_setting_get)

    @pytest.mark.parametrize("is_authenticated,is_supported", [(True, False), (False, True)])
    async def test_supports_unauthenticated_accounts(
        self, db: InfrahubDatabase, branch: Branch, is_authenticated, is_supported
    ):
        self.account_session.authenticated = is_authenticated

        has_support = await self.checker.supports(db=db, account_session=self.account_session, branch=branch)

        assert is_supported is has_support

    @pytest.mark.parametrize("anonymous_setting,query_has_mutations", [(False, False), (False, True), (True, True)])
    async def test_failures_raise_error(
        self, db: InfrahubDatabase, branch: Branch, anonymous_setting, query_has_mutations
    ):
        self.mock_anonymous_setting_get.return_value = anonymous_setting
        self.graphql_query.contains_mutation = query_has_mutations

        with pytest.raises(AuthorizationError):
            await self.checker.check(
                db=db,
                account_session=self.account_session,
                analyzed_query=self.graphql_query,
                query_parameters=self.query_parameters,
                branch=branch,
            )

    async def test_check_passes(self, db: InfrahubDatabase, branch: Branch):
        self.mock_anonymous_setting_get.return_value = True
        self.graphql_query.contains_mutation = False

        await self.checker.check(
            db=db,
            account_session=self.account_session,
            analyzed_query=self.graphql_query,
            query_parameters=self.query_parameters,
            branch=branch,
        )
