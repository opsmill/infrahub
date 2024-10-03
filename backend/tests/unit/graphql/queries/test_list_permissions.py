from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from graphql import graphql

from infrahub.auth import AccountSession, AuthType
from infrahub.core.account import ObjectPermission
from infrahub.core.constants import (
    InfrahubKind,
    PermissionAction,
    PermissionDecision,
)
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.permissions.local_backend import LocalPermissionBackend

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from tests.unit.graphql.conftest import PermissionsHelper


QUERY_TAGS = """
query {
  BuiltinTag {
    permissions {
        count
        edges {
            node {
                kind
                create
                update
                delete
                view
            }
        }
    }
  }
}
"""

REPOSITORY_QUERY = """
query {
  CoreGenericRepository {
    permissions {
        count
        edges {
            node {
                kind
                create
                update
                delete
                view
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
                branch="*",
                namespace="Builtin",
                name="*",
                action=PermissionAction.VIEW.value,
                decision=PermissionDecision.ALLOW.value,
            ),
            ObjectPermission(
                id="",
                branch="*",
                namespace="Builtin",
                name="*",
                action=PermissionAction.ADD.value,
                decision=PermissionDecision.ALLOW.value,
            ),
            ObjectPermission(
                id="",
                branch="*",
                namespace="Builtin",
                name="*",
                action=PermissionAction.DELETE.value,
                decision=PermissionDecision.ALLOW.value,
            ),
            ObjectPermission(
                id="",
                branch="*",
                namespace="Core",
                name="*",
                action=PermissionAction.ANY.value,
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

    async def test_first_account_tags_main_branch(
        self, db: InfrahubDatabase, permissions_helper: PermissionsHelper
    ) -> None:
        """In the main branch the first account doesn't have the permission to make changes"""
        session = AccountSession(
            authenticated=True,
            account_id=permissions_helper.first.id,
            session_id=str(uuid4()),
            auth_type=AuthType.JWT,
        )
        gql_params = prepare_graphql_params(
            db=db, include_mutation=True, branch=permissions_helper.default_branch, account_session=session
        )

        result = await graphql(
            schema=gql_params.schema,
            source=QUERY_TAGS,
            context_value=gql_params.context,
        )

        assert not result.errors
        assert result.data
        assert result.data["BuiltinTag"]["permissions"]["count"] == 1
        assert result.data["BuiltinTag"]["permissions"]["edges"][0] == {
            "node": {"kind": "BuiltinTag", "create": "DENY", "update": "DENY", "delete": "DENY", "view": "ALLOW"}
        }

    async def test_first_account_tags_non_main_branch(
        self, db: InfrahubDatabase, permissions_helper: PermissionsHelper
    ) -> None:
        """In other branches the permissions for the first account is less restrictive"""
        branch2 = await create_branch(branch_name="pr-12345", db=db)
        session = AccountSession(
            authenticated=True,
            account_id=permissions_helper.first.id,
            session_id=str(uuid4()),
            auth_type=AuthType.JWT,
        )
        gql_params = prepare_graphql_params(db=db, include_mutation=True, branch=branch2, account_session=session)

        result = await graphql(
            schema=gql_params.schema,
            source=QUERY_TAGS,
            context_value=gql_params.context,
        )

        assert not result.errors
        assert result.data
        assert result.data["BuiltinTag"]["permissions"]["count"] == 1
        assert result.data["BuiltinTag"]["permissions"]["edges"][0] == {
            "node": {"kind": "BuiltinTag", "create": "ALLOW", "update": "DENY", "delete": "ALLOW", "view": "ALLOW"}
        }

    async def test_first_account_list_permissions_for_generics(
        self, db: InfrahubDatabase, permissions_helper: PermissionsHelper
    ) -> None:
        """In the main branch the first account doesn't have the permission to make changes"""
        session = AccountSession(
            authenticated=True,
            account_id=permissions_helper.first.id,
            session_id=str(uuid4()),
            auth_type=AuthType.JWT,
        )
        gql_params = prepare_graphql_params(
            db=db, include_mutation=True, branch=permissions_helper.default_branch, account_session=session
        )

        result = await graphql(
            schema=gql_params.schema,
            source=REPOSITORY_QUERY,
            context_value=gql_params.context,
        )

        assert not result.errors
        assert result.data
        assert result.data["CoreGenericRepository"]["permissions"]["count"] == 3
        assert {
            "node": {
                "kind": "CoreGenericRepository",
                "create": "DENY",
                "update": "DENY",
                "delete": "DENY",
                "view": "ALLOW",
            }
        } in result.data["CoreGenericRepository"]["permissions"]["edges"]
        assert {
            "node": {
                "kind": "CoreRepository",
                "create": "DENY",
                "update": "DENY",
                "delete": "DENY",
                "view": "ALLOW",
            }
        } in result.data["CoreGenericRepository"]["permissions"]["edges"]
        assert {
            "node": {
                "kind": "CoreReadOnlyRepository",
                "create": "DENY",
                "update": "DENY",
                "delete": "DENY",
                "view": "ALLOW",
            }
        } in result.data["CoreGenericRepository"]["permissions"]["edges"]
