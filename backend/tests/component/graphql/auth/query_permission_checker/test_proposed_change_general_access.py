from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from infrahub.auth import AccountSession, AuthType
from infrahub.core.account import ObjectPermission
from infrahub.core.constants import (
    GlobalPermissions,
    InfrahubKind,
    PermissionAction,
    PermissionDecision,
)
from infrahub.core.node import Node
from infrahub.exceptions import PermissionDeniedError
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.auth.query_permission_checker.default_branch_checker import DefaultBranchPermissionChecker
from infrahub.graphql.auth.query_permission_checker.interface import CheckerResolution
from infrahub.graphql.initialization import GraphqlContext, GraphqlParams
from infrahub.graphql.resolvers.account_metadata import AccountMetadataResolver
from infrahub.permissions import PermissionManager

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from tests.component.graphql.conftest import PermissionsHelper


class TestProposedChangeGeneralAccessDefaultBranch:
    """Test that a user with General Access role permissions can create a ProposedChange.

    The General Access role does NOT include EDIT_DEFAULT_BRANCH permission.
    ProposedChange creation is a mutation on the default branch, so the
    DefaultBranchPermissionChecker must exempt it, similar to BranchCreate.
    """

    async def test_setup(
        self,
        db: InfrahubDatabase,
        default_permission_backend: None,
        register_core_models_schema: None,
        default_branch: Branch,
        first_account: CoreAccount,
        permissions_helper: PermissionsHelper,
    ) -> None:
        permissions_helper._default_branch = default_branch

        # Set up permissions matching the General Access role:
        # - MANAGE_REPOSITORIES, MANAGE_SCHEMA, MERGE_PROPOSED_CHANGE (global)
        # - VIEW */* ALLOW_ALL (object)
        # - ANY */* ALLOW_OTHER (object)
        # Notably NO EDIT_DEFAULT_BRANCH permission.
        global_permissions = []
        for action in (
            GlobalPermissions.MANAGE_REPOSITORIES,
            GlobalPermissions.MANAGE_SCHEMA,
            GlobalPermissions.MERGE_PROPOSED_CHANGE,
        ):
            perm = await Node.init(db=db, schema=InfrahubKind.GLOBALPERMISSION)
            await perm.new(db=db, action=action.value, decision=PermissionDecision.ALLOW_ALL.value)
            await perm.save(db=db)
            global_permissions.append(perm)

        view_permission = await Node.init(db=db, schema=InfrahubKind.OBJECTPERMISSION)
        await view_permission.new(
            db=db,
            namespace="*",
            name="*",
            action=PermissionAction.VIEW.value,
            decision=PermissionDecision.ALLOW_ALL.value,
        )
        await view_permission.save(db=db)

        modify_permission = await Node.init(db=db, schema=InfrahubKind.OBJECTPERMISSION)
        await modify_permission.new(
            db=db,
            namespace="*",
            name="*",
            action=PermissionAction.ANY.value,
            decision=PermissionDecision.ALLOW_OTHER.value,
        )
        await modify_permission.save(db=db)

        role = await Node.init(db=db, schema=InfrahubKind.ACCOUNTROLE)
        await role.new(
            db=db,
            name="General Access",
            permissions=[*global_permissions, view_permission, modify_permission],
        )
        await role.save(db=db)

        group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
        await group.new(db=db, name="general_access_group", roles=[role])
        await group.save(db=db)

        await group.members.add(db=db, data={"id": first_account.id})
        await group.members.save(db=db)

        permissions_helper._first = first_account

    async def test_proposed_change_create_not_blocked_by_default_branch_checker(
        self,
        db: InfrahubDatabase,
        default_permission_backend: None,
        permissions_helper: PermissionsHelper,
    ) -> None:
        """A General Access user creating a ProposedChange should not be blocked by the
        DefaultBranchPermissionChecker, because ProposedChangeCreate should be exempt
        from the EDIT_DEFAULT_BRANCH requirement (like BranchCreate is)."""
        checker = DefaultBranchPermissionChecker()
        session = AccountSession(
            authenticated=True, account_id=permissions_helper.first.id, session_id=str(uuid4()), auth_type=AuthType.JWT
        )
        permission_manager = PermissionManager(account_session=session)
        await permission_manager.load_permissions(db=db, branch=permissions_helper.default_branch)

        graphql_query = MagicMock(spec=InfrahubGraphQLQueryAnalyzer)
        graphql_query.branch = MagicMock()
        graphql_query.branch.name = "main"
        graphql_query.contains_mutation = True
        graphql_query.operation_names = ["ProposedChangeCreate"]

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

        # This should NOT raise PermissionDeniedError - the checker should let it through
        resolution = await checker.check(
            db=db,
            account_session=session,
            analyzed_query=graphql_query,
            query_parameters=query_parameters,
            branch=permissions_helper.default_branch,
        )
        assert resolution == CheckerResolution.NEXT_CHECKER
