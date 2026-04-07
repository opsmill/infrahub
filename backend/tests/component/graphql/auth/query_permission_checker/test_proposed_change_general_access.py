from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from infrahub.auth import AccountSession, AuthType
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_default_role
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.auth.query_permission_checker.checker import GraphQLQueryPermissionChecker
from infrahub.graphql.auth.query_permission_checker.default_branch_checker import DefaultBranchPermissionChecker
from infrahub.graphql.auth.query_permission_checker.interface import CheckerResolution
from infrahub.graphql.auth.query_permission_checker.object_permission_checker import ObjectPermissionChecker
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.permissions import PermissionManager
from tests.component.graphql.auth.query_permission_checker.conftest import build_graphql_query_mock, build_query_params

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from tests.component.graphql.conftest import PermissionsHelper


MUTATION_PROPOSED_CHANGE_CREATE = """
mutation CoreProposedChangeCreate {
  CoreProposedChangeCreate(data: {
    name: {value: "test-pc"}
    source_branch: {value: "feature-branch"}
  }) {
    ok
    object {
      id
    }
  }
}
"""


class TestProposedChangeGeneralAccessPermissions:
    """Test that a user with General Access role permissions can create a ProposedChange.

    The General Access role has (after fix):
    - Global: MANAGE_REPOSITORIES, MANAGE_SCHEMA, MERGE_PROPOSED_CHANGE
    - Object: VIEW */* ALLOW_ALL, ANY */* ALLOW_OTHER, Core/ProposedChange/create ALLOW_DEFAULT
    - Notably does NOT have EDIT_DEFAULT_BRANCH

    ProposedChange creation targets the default branch but is a workflow operation
    (like BranchCreate), not "editing data in the default branch." Both the
    DefaultBranchPermissionChecker and ObjectPermissionChecker must allow it.
    """

    @pytest.fixture(autouse=True)
    async def setup(
        self,
        db: InfrahubDatabase,
        default_permission_backend: None,
        register_core_models_schema: None,
        default_branch: Branch,
        first_account: CoreAccount,
        permissions_helper: PermissionsHelper,
    ) -> None:
        permissions_helper._default_branch = default_branch

        role = await create_default_role(db=db)

        group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
        await group.new(db=db, name="general_access_group", roles=[role])
        await group.save(db=db)

        await group.members.add(db=db, data={"id": first_account.id})
        await group.members.save(db=db)

        permissions_helper._first = first_account

    async def test_proposed_change_create_not_blocked_by_default_branch_checker(
        self,
        db: InfrahubDatabase,
        permissions_helper: PermissionsHelper,
    ) -> None:
        """ProposedChangeCreate should be exempt from EDIT_DEFAULT_BRANCH requirement.

        The DefaultBranchPermissionChecker blocks mutations on the default branch unless
        the user has EDIT_DEFAULT_BRANCH or the operation is in exempt_operations.
        ProposedChange creation is a workflow operation (like BranchCreate) and should
        be exempt.
        """
        checker = DefaultBranchPermissionChecker()
        session = AccountSession(
            authenticated=True, account_id=permissions_helper.first.id, session_id=str(uuid4()), auth_type=AuthType.JWT
        )
        permission_manager = PermissionManager(account_session=session)
        await permission_manager.load_permissions(db=db, branch=permissions_helper.default_branch)

        graphql_query = build_graphql_query_mock(
            branch_name="main", contains_mutation=True, operation_names=["CoreProposedChangeCreate"]
        )
        query_parameters = build_query_params(session, permission_manager)

        resolution = await checker.check(
            db=db,
            account_session=session,
            analyzed_query=graphql_query,
            query_parameters=query_parameters,
            branch=permissions_helper.default_branch,
        )
        assert resolution == CheckerResolution.NEXT_CHECKER

    async def test_proposed_change_create_allowed_by_full_permission_chain(
        self,
        db: InfrahubDatabase,
        permissions_helper: PermissionsHelper,
    ) -> None:
        """The full permission checker chain should allow ProposedChange creation for General Access.

        The test setup includes a CoreProposedChange-specific ALLOW_DEFAULT object permission. Even with this permission present,
        the DefaultBranchPermissionChecker still blocks the operation because
        CoreProposedChangeCreate is not in its exempt_operations list.
        """
        session = AccountSession(
            authenticated=True, account_id=permissions_helper.first.id, session_id=str(uuid4()), auth_type=AuthType.JWT
        )

        gql_params = await prepare_graphql_params(
            db=db, include_mutation=True, branch=permissions_helper.default_branch, account_session=session
        )
        schema_branch = registry.schema.get_schema_branch(name=permissions_helper.default_branch.name)
        analyzed_query = InfrahubGraphQLQueryAnalyzer(
            query=MUTATION_PROPOSED_CHANGE_CREATE,
            schema=gql_params.schema,
            branch=permissions_helper.default_branch,
            schema_branch=schema_branch,
        )

        checker_chain = GraphQLQueryPermissionChecker([DefaultBranchPermissionChecker(), ObjectPermissionChecker()])

        # Expected: full chain allows the operation (no error raised)
        await checker_chain.check(
            db=db,
            account_session=session,
            analyzed_query=analyzed_query,
            branch=permissions_helper.default_branch,
            query_parameters=gql_params,
        )
