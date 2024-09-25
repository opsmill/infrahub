from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from infrahub.auth import AccountSession, AuthType
from infrahub.core.constants import AccountRole, GlobalPermissions, InfrahubKind
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.graphql import GraphqlParams
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.auth.query_permission_checker.interface import CheckerResolution
from infrahub.graphql.auth.query_permission_checker.super_admin_checker import SuperAdminPermissionChecker
from infrahub.permissions.local_backend import LocalPermissionBackend

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase


class PermissionsHelper:
    def __init__(self) -> None:
        self._first: None | CoreAccount = None
        self._second: None | CoreAccount = None
        self._default_branch: None | Branch = None

    @property
    def first(self) -> CoreAccount:
        if self._first:
            return self._first

        raise NotImplementedError()

    @property
    def second(self) -> CoreAccount:
        if self._second:
            return self._second

        raise NotImplementedError()

    @property
    def default_branch(self) -> Branch:
        if self._default_branch:
            return self._default_branch


permission_helper = PermissionsHelper()


class TestSuperAdminPermission:
    async def test_setup(
        self,
        db: InfrahubDatabase,
        register_core_models_schema: None,
        default_branch: Branch,
        first_account: CoreAccount,
        second_account: CoreAccount,
    ):
        registry.permission_backends = [LocalPermissionBackend()]
        permission_helper._default_branch = default_branch

        permission = await Node.init(db=db, schema=InfrahubKind.GLOBALPERMISSION)
        await permission.new(
            db=db, name=GlobalPermissions.SUPER_ADMIN.value, action=GlobalPermissions.SUPER_ADMIN.value
        )
        await permission.save(db=db)

        role = await Node.init(db=db, schema=InfrahubKind.ACCOUNTROLE)
        await role.new(db=db, name="admin", permissions=[permission])
        await role.save(db=db)

        group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
        await group.new(db=db, name="admin", roles=[role])
        await group.save(db=db)

        await group.members.add(db=db, data={"id": first_account.id})
        await group.members.save(db=db)

        permission_helper._first = first_account
        permission_helper._second = second_account

    @pytest.mark.parametrize(
        "user",
        [
            AccountSession(account_id="abc", auth_type=AuthType.JWT, role=AccountRole.ADMIN),
            AccountSession(authenticated=False, account_id="anonymous", auth_type=AuthType.NONE),
        ],
    )
    async def test_supports_super_admin_permission_accounts(self, user: AccountSession, db: InfrahubDatabase):
        checker = SuperAdminPermissionChecker()
        is_supported = await checker.supports(db=db, account_session=user, branch=permission_helper.default_branch)
        assert is_supported == user.authenticated

    async def test_account_with_permission(self, db: InfrahubDatabase):
        checker = SuperAdminPermissionChecker()
        session = AccountSession(
            authenticated=True, account_id=permission_helper.first.id, session_id=str(uuid4()), auth_type=AuthType.JWT
        )
        resolution = await checker.check(
            db=db,
            account_session=session,
            analyzed_query=AsyncMock(spec=InfrahubGraphQLQueryAnalyzer),
            query_parameters=MagicMock(spec=GraphqlParams),
            branch=permission_helper.default_branch,
        )
        assert resolution == CheckerResolution.TERMINATE

    async def test_account_without_permission(self, db: InfrahubDatabase):
        checker = SuperAdminPermissionChecker()
        session = AccountSession(
            authenticated=True, account_id=permission_helper.second.id, session_id=str(uuid4()), auth_type=AuthType.JWT
        )
        resolution = await checker.check(
            db=db,
            account_session=session,
            analyzed_query=AsyncMock(spec=InfrahubGraphQLQueryAnalyzer),
            query_parameters=MagicMock(spec=GraphqlParams),
            branch=permission_helper.default_branch,
        )
        assert resolution == CheckerResolution.NEXT_CHECKER
