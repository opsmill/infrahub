from unittest.mock import AsyncMock, MagicMock

import pytest

from infrahub import config
from infrahub.auth import AccountSession, AuthType
from infrahub.core.constants import AccountRole, GlobalPermissions
from infrahub.exceptions import PermissionDeniedError
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.auth.query_permission_checker.default_branch_checker import DefaultBranchPermissionChecker


class TestDefaultBranchPermissionChecker:
    def setup_method(self):
        self.account_session = AccountSession(account_id="abc", auth_type=AuthType.JWT, role=AccountRole.ADMIN)
        self.graphql_query = AsyncMock(spec=InfrahubGraphQLQueryAnalyzer)
        self.checker = DefaultBranchPermissionChecker()

    @pytest.mark.parametrize(
        "user",
        [
            AccountSession(
                account_id="123",
                auth_type=AuthType.JWT,
                role=AccountRole.ADMIN,
                permissions={"global_permissions": [GlobalPermissions.EDIT_DEFAULT_BRANCH.value]},
            ),
            AccountSession(account_id="abc", auth_type=AuthType.JWT, role=AccountRole.ADMIN),
            AccountSession(authenticated=False, account_id="anonymous", auth_type=AuthType.NONE),
        ],
    )
    async def test_supports_default_branch_permission_accounts(self, user):
        is_supported = await self.checker.supports(user)
        assert is_supported == user.authenticated

    @pytest.mark.parametrize(
        "can_edit_default_branch,contains_mutations,branch_name",
        [
            (True, True, "main"),
            (True, False, "main"),
            (False, True, "main"),
            (False, False, "main"),
            (True, True, "not_default_branch"),
            (True, False, "not_default_branch"),
            (False, True, "not_default_branch"),
            (False, False, "not_default_branch"),
        ],
    )
    async def test_raise_if_not_permission(self, can_edit_default_branch, contains_mutations, branch_name):
        self.checker.can_edit_default_branch = can_edit_default_branch
        self.graphql_query.contains_mutations = contains_mutations
        self.graphql_query.operation_name = "CreateTags"
        self.graphql_query.branch = MagicMock()
        self.graphql_query.branch.name = branch_name

        if contains_mutations and not can_edit_default_branch and branch_name == config.SETTINGS.initial.default_branch:
            with pytest.raises(
                PermissionDeniedError, match=r"You are not allowed to change data in the default branch"
            ):
                await self.checker.check(self.graphql_query)
