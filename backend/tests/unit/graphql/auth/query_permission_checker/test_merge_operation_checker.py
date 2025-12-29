from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from infrahub.auth import AccountSession, AuthType
from infrahub.core.constants import GlobalPermissions, InfrahubKind, PermissionDecision
from infrahub.core.node import Node
from infrahub.exceptions import PermissionDeniedError
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.auth.query_permission_checker.interface import CheckerResolution
from infrahub.graphql.auth.query_permission_checker.merge_operation_checker import MergeBranchPermissionChecker
from infrahub.graphql.initialization import GraphqlContext, GraphqlParams
from infrahub.graphql.resolvers.account_metadata import AccountMetadataResolver
from infrahub.permissions import PermissionManager

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from tests.unit.graphql.conftest import PermissionsHelper


class TestMergeBranchPermission:
    async def test_setup(
        self,
        db: InfrahubDatabase,
        default_permission_backend: None,
        register_core_models_schema: None,
        default_branch: Branch,
        permissions_helper: PermissionsHelper,
        first_account: CoreAccount,
        second_account: CoreAccount,
    ) -> None:
        permissions_helper._default_branch = default_branch

        permission = await Node.init(db=db, schema=InfrahubKind.GLOBALPERMISSION)
        await permission.new(
            db=db, action=GlobalPermissions.MERGE_BRANCH.value, decision=PermissionDecision.ALLOW_ALL.value
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

        permissions_helper._first = first_account
        permissions_helper._second = second_account

    @pytest.mark.parametrize(
        "user",
        [
            AccountSession(account_id="abc", auth_type=AuthType.JWT),
            AccountSession(authenticated=False, account_id="anonymous", auth_type=AuthType.NONE),
        ],
    )
    async def test_supports_merge_branch_permission_accounts(
        self, user: AccountSession, db: InfrahubDatabase, permissions_helper: PermissionsHelper
    ) -> None:
        checker = MergeBranchPermissionChecker()
        with patch("infrahub.config.SETTINGS.main.allow_anonymous_access", False):
            is_supported = await checker.supports(db=db, account_session=user, branch=permissions_helper.default_branch)
            assert is_supported == user.authenticated

    @pytest.mark.parametrize(
        "operation_name,checker_resolution",
        [("BranchMerge", CheckerResolution.TERMINATE), ("BuiltinTagCreate", CheckerResolution.NEXT_CHECKER)],
    )
    async def test_account_with_permission(
        self,
        operation_name: str,
        checker_resolution: CheckerResolution | None,
        db: InfrahubDatabase,
        default_permission_backend: None,
        permissions_helper: PermissionsHelper,
    ) -> None:
        checker = MergeBranchPermissionChecker()
        session = AccountSession(
            authenticated=True, account_id=permissions_helper.first.id, session_id=str(uuid4()), auth_type=AuthType.JWT
        )
        permission_manager = PermissionManager(account_session=session)
        await permission_manager.load_permissions(db=db, branch=permissions_helper.default_branch)

        graphql_query = AsyncMock(spec=InfrahubGraphQLQueryAnalyzer)
        graphql_query.operation_name = "Foo"
        graphql_query.operations = [MagicMock()]
        graphql_query.operations[0].name = operation_name

        graphql_context = MagicMock(spec=GraphqlContext)
        graphql_context.permissions = permission_manager
        query_parameters = MagicMock(spec=GraphqlParams)
        query_parameters.context = graphql_context

        resolution = await checker.check(
            db=db,
            account_session=session,
            analyzed_query=graphql_query,
            query_parameters=query_parameters,
            branch=permissions_helper.default_branch,
        )
        assert resolution == checker_resolution

    @pytest.mark.parametrize(
        "operation_name,checker_resolution",
        [("BranchMerge", None), ("BuiltinTagCreate", CheckerResolution.NEXT_CHECKER)],
    )
    async def test_account_without_permission(
        self,
        operation_name: str,
        checker_resolution: CheckerResolution | None,
        db: InfrahubDatabase,
        permissions_helper: PermissionsHelper,
    ) -> None:
        checker = MergeBranchPermissionChecker()
        session = AccountSession(
            authenticated=True, account_id=permissions_helper.second.id, session_id=str(uuid4()), auth_type=AuthType.JWT
        )
        permission_manager = PermissionManager(account_session=session)
        await permission_manager.load_permissions(db=db, branch=permissions_helper.default_branch)

        graphql_query = AsyncMock(spec=InfrahubGraphQLQueryAnalyzer)
        graphql_query.operation_name = "Foo"
        graphql_query.operations = [MagicMock()]
        graphql_query.operations[0].name = operation_name

        graphql_context = GraphqlContext(
            db=MagicMock(),
            branch=MagicMock(),
            types=MagicMock(),
            single_relationship_resolver=MagicMock(),
            many_relationship_resolver=MagicMock(),
            account_metadata_resolver=AccountMetadataResolver(),
            account_session=session,
            permissions=permission_manager,
        )
        query_parameters = GraphqlParams(schema=MagicMock(), context=graphql_context)

        if checker_resolution is None:
            with pytest.raises(PermissionDeniedError, match=r"You are not allowed to merge a branch"):
                await checker.check(
                    db=db,
                    account_session=session,
                    analyzed_query=graphql_query,
                    query_parameters=query_parameters,
                    branch=permissions_helper.default_branch,
                )
        else:
            resolution = await checker.check(
                db=db,
                account_session=session,
                analyzed_query=graphql_query,
                query_parameters=query_parameters,
                branch=permissions_helper.default_branch,
            )
            assert resolution == checker_resolution
