from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from infrahub.auth import AccountSession, AuthType
from infrahub.core.account import ObjectPermission
from infrahub.core.constants import (
    InfrahubKind,
    PermissionAction,
    PermissionDecision,
)
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.exceptions import PermissionDeniedError
from infrahub.graphql import prepare_graphql_params
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.auth.query_permission_checker.object_permission_checker import ObjectPermissionChecker
from infrahub.permissions.local_backend import LocalPermissionBackend

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from tests.unit.graphql.conftest import PermissionsHelper


QUERY_TAGS = """
query {
  BuiltinTag {
    edges {
      node {
        display_label
      }
    }
  }
}
"""

QUERY_REPOS = """
query {
  CoreRepository {
    edges {
      node {
        display_label
      }
    }
  }
}
"""

QUERY_GRAPHQL = """
query {
  CoreGraphQLQuery {
    edges {
      node {
        display_label
      }
    }
  }
}
"""

QUERY_GRAPHQL_AND_REPO = """
query {
  CoreGraphQLQuery {
    edges {
      node {
        display_label
        repository {
          node {
            display_label
          }
        }
      }
    }
  }
}
"""


class TestObjectPermissions:
    async def test_setup(
        self,
        db: InfrahubDatabase,
        register_core_models_schema: None,
        default_branch: Branch,
        permissions_helper: PermissionsHelper,
        first_account: CoreAccount,
    ):
        permissions_helper._first = first_account
        permissions_helper._default_branch = default_branch
        registry.permission_backends = [LocalPermissionBackend()]

        permissions = []
        for object_permission in [
            ObjectPermission(
                id="",
                branch="main",
                namespace="Builtin",
                name="*",
                action=PermissionAction.ANY.value,
                decision=PermissionDecision.ALLOW.value,
            ),
            ObjectPermission(
                id="",
                branch="main",
                namespace="Core",
                name="GraphQLQuery",
                action=PermissionAction.VIEW.value,
                decision=PermissionDecision.ALLOW.value,
            ),
        ]:
            obj = await Node.init(db=db, schema=InfrahubKind.OBJECTPERMISSION)
            await obj.new(
                db=db,
                branch=object_permission.branch,
                namespace=object_permission.namespace,
                name=object_permission.name,
                action=object_permission.action,
                decision=object_permission.decision,
            )
            await obj.save(db=db)
            permissions.append(obj)

        role = await Node.init(db=db, schema=InfrahubKind.ACCOUNTROLE)
        await role.new(db=db, name="admin", permissions=permissions)
        await role.save(db=db)

        group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
        await group.new(db=db, name="admin", roles=[role])
        await group.save(db=db)

        await group.members.add(db=db, data={"id": first_account.id})
        await group.members.save(db=db)

    async def test_first_account_tags(self, db: InfrahubDatabase, permissions_helper: PermissionsHelper) -> None:
        gql_params = prepare_graphql_params(db=db, include_mutation=True, branch=permissions_helper.default_branch)
        analyzed_query = InfrahubGraphQLQueryAnalyzer(
            query=QUERY_TAGS, schema=gql_params.schema, branch=permissions_helper.default_branch
        )
        perms = ObjectPermissionChecker()
        session = AccountSession(
            authenticated=True,
            account_id=permissions_helper.first.id,
            session_id=str(uuid4()),
            auth_type=AuthType.JWT,
        )

        await perms.check(
            db=db,
            account_session=session,
            analyzed_query=analyzed_query,
            branch=permissions_helper.default_branch,
            query_parameters=gql_params,
        )

    async def test_first_account_repos(self, db: InfrahubDatabase, permissions_helper: PermissionsHelper) -> None:
        gql_params = prepare_graphql_params(db=db, include_mutation=True, branch=permissions_helper.default_branch)
        analyzed_query = InfrahubGraphQLQueryAnalyzer(
            query=QUERY_REPOS, schema=gql_params.schema, branch=permissions_helper.default_branch
        )
        perms = ObjectPermissionChecker()
        session = AccountSession(
            authenticated=True,
            account_id=permissions_helper.first.id,
            session_id=str(uuid4()),
            auth_type=AuthType.JWT,
        )

        with pytest.raises(
            PermissionDeniedError,
            match="You do not have the following permission: object:main:Core:Repository:view:allow",
        ):
            await perms.check(
                db=db,
                account_session=session,
                analyzed_query=analyzed_query,
                branch=permissions_helper.default_branch,
                query_parameters=gql_params,
            )

    async def test_first_account_graphql(self, db: InfrahubDatabase, permissions_helper: PermissionsHelper) -> None:
        """The user should have permissions to list GraphQLQueries."""
        gql_params = prepare_graphql_params(db=db, include_mutation=True, branch=permissions_helper.default_branch)
        analyzed_query = InfrahubGraphQLQueryAnalyzer(
            query=QUERY_GRAPHQL, schema=gql_params.schema, branch=permissions_helper.default_branch
        )
        perms = ObjectPermissionChecker()
        session = AccountSession(
            authenticated=True,
            account_id=permissions_helper.first.id,
            session_id=str(uuid4()),
            auth_type=AuthType.JWT,
        )

        await perms.check(
            db=db,
            account_session=session,
            analyzed_query=analyzed_query,
            branch=permissions_helper.default_branch,
            query_parameters=gql_params,
        )

    async def test_first_account_graphql_and_repos(
        self, db: InfrahubDatabase, permissions_helper: PermissionsHelper
    ) -> None:
        """The user should have permissions to list GraphQLQueries but not repositories linked to them"""
        gql_params = prepare_graphql_params(db=db, include_mutation=True, branch=permissions_helper.default_branch)
        analyzed_query = InfrahubGraphQLQueryAnalyzer(
            query=QUERY_GRAPHQL_AND_REPO, schema=gql_params.schema, branch=permissions_helper.default_branch
        )
        perms = ObjectPermissionChecker()
        session = AccountSession(
            authenticated=True,
            account_id=permissions_helper.first.id,
            session_id=str(uuid4()),
            auth_type=AuthType.JWT,
        )

        with pytest.raises(PermissionDeniedError, match="Repository:view:allow"):
            await perms.check(
                db=db,
                account_session=session,
                analyzed_query=analyzed_query,
                branch=permissions_helper.default_branch,
                query_parameters=gql_params,
            )
