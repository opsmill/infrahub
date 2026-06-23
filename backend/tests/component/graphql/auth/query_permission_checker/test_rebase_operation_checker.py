from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.core import registry
from infrahub.core.constants import GlobalPermissions, InfrahubKind, PermissionDecision
from infrahub.core.node import Node
from infrahub.exceptions import PermissionDeniedError
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.auth.query_permission_checker.interface import CheckerResolution
from infrahub.graphql.auth.query_permission_checker.rebase_operation_checker import RebaseBranchPermissionChecker
from infrahub.graphql.initialization import prepare_graphql_params

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from tests.component.graphql.conftest import PermissionsHelper


REBASE_QUERY = """
mutation {
    BranchRebase(data: { name: "branch1" }) {
        ok
    }
}
"""

UNRELATED_QUERY = """
mutation {
    BuiltinTagCreate(data: { name: { value: "tag1" } }) {
        ok
    }
}
"""


class TestRebaseBranchPermission:
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
            db=db, action=GlobalPermissions.REBASE_BRANCH.value, decision=PermissionDecision.ALLOW_ALL.value
        )
        await permission.save(db=db)

        role = await Node.init(db=db, schema=InfrahubKind.ACCOUNTROLE)
        await role.new(db=db, name="rebaser", permissions=[permission])
        await role.save(db=db)

        group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
        await group.new(db=db, name="rebaser", roles=[role])
        await group.save(db=db)

        await group.members.add(db=db, data={"id": first_account.id})
        await group.members.save(db=db)

        permissions_helper._first = first_account
        permissions_helper._second = second_account

    async def test_supports_authenticated_account(
        self,
        db: InfrahubDatabase,
        permissions_helper: PermissionsHelper,
    ) -> None:
        checker = RebaseBranchPermissionChecker()
        user = AccountSession(authenticated=True, account_id="abc", auth_type=AuthType.JWT)
        is_supported = await checker.supports(db=db, account_session=user, branch=permissions_helper.default_branch)
        assert is_supported is True

    async def test_account_with_permission_can_rebase(
        self,
        db: InfrahubDatabase,
        default_permission_backend: None,
        permissions_helper: PermissionsHelper,
    ) -> None:
        checker = RebaseBranchPermissionChecker()
        session = AccountSession(
            authenticated=True, account_id=permissions_helper.first.id, session_id=str(uuid4()), auth_type=AuthType.JWT
        )
        gql_params = await prepare_graphql_params(
            db=db, branch=permissions_helper.default_branch, account_session=session
        )
        schema_branch = registry.schema.get_schema_branch(name=permissions_helper.default_branch.name)
        analyzed_query = InfrahubGraphQLQueryAnalyzer(
            query=REBASE_QUERY,
            schema=gql_params.schema,
            branch=permissions_helper.default_branch,
            schema_branch=schema_branch,
        )

        resolution = await checker.check(
            db=db,
            account_session=session,
            analyzed_query=analyzed_query,
            query_parameters=gql_params,
            branch=permissions_helper.default_branch,
        )
        assert resolution == CheckerResolution.TERMINATE

    async def test_account_with_permission_skips_unrelated_operation(
        self,
        db: InfrahubDatabase,
        default_permission_backend: None,
        permissions_helper: PermissionsHelper,
    ) -> None:
        checker = RebaseBranchPermissionChecker()
        session = AccountSession(
            authenticated=True, account_id=permissions_helper.first.id, session_id=str(uuid4()), auth_type=AuthType.JWT
        )
        gql_params = await prepare_graphql_params(
            db=db, branch=permissions_helper.default_branch, account_session=session
        )
        schema_branch = registry.schema.get_schema_branch(name=permissions_helper.default_branch.name)
        analyzed_query = InfrahubGraphQLQueryAnalyzer(
            query=UNRELATED_QUERY,
            schema=gql_params.schema,
            branch=permissions_helper.default_branch,
            schema_branch=schema_branch,
        )

        resolution = await checker.check(
            db=db,
            account_session=session,
            analyzed_query=analyzed_query,
            query_parameters=gql_params,
            branch=permissions_helper.default_branch,
        )
        assert resolution == CheckerResolution.NEXT_CHECKER

    async def test_account_without_permission_is_denied(
        self,
        db: InfrahubDatabase,
        default_permission_backend: None,
        permissions_helper: PermissionsHelper,
    ) -> None:
        checker = RebaseBranchPermissionChecker()
        session = AccountSession(
            authenticated=True, account_id=permissions_helper.second.id, session_id=str(uuid4()), auth_type=AuthType.JWT
        )
        gql_params = await prepare_graphql_params(
            db=db, branch=permissions_helper.default_branch, account_session=session
        )
        schema_branch = registry.schema.get_schema_branch(name=permissions_helper.default_branch.name)
        analyzed_query = InfrahubGraphQLQueryAnalyzer(
            query=REBASE_QUERY,
            schema=gql_params.schema,
            branch=permissions_helper.default_branch,
            schema_branch=schema_branch,
        )

        with pytest.raises(PermissionDeniedError, match=r"You are not allowed to rebase a branch"):
            await checker.check(
                db=db,
                account_session=session,
                analyzed_query=analyzed_query,
                query_parameters=gql_params,
                branch=permissions_helper.default_branch,
            )

    async def test_account_without_permission_skips_unrelated_operation(
        self,
        db: InfrahubDatabase,
        default_permission_backend: None,
        permissions_helper: PermissionsHelper,
    ) -> None:
        checker = RebaseBranchPermissionChecker()
        session = AccountSession(
            authenticated=True, account_id=permissions_helper.second.id, session_id=str(uuid4()), auth_type=AuthType.JWT
        )
        gql_params = await prepare_graphql_params(
            db=db, branch=permissions_helper.default_branch, account_session=session
        )
        schema_branch = registry.schema.get_schema_branch(name=permissions_helper.default_branch.name)
        analyzed_query = InfrahubGraphQLQueryAnalyzer(
            query=UNRELATED_QUERY,
            schema=gql_params.schema,
            branch=permissions_helper.default_branch,
            schema_branch=schema_branch,
        )

        resolution = await checker.check(
            db=db,
            account_session=session,
            analyzed_query=analyzed_query,
            query_parameters=gql_params,
            branch=permissions_helper.default_branch,
        )
        assert resolution == CheckerResolution.NEXT_CHECKER
