from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from infrahub.auth import AccountSession, AuthType
from infrahub.core.account import ObjectPermission
from infrahub.core.constants import InfrahubKind, PermissionAction
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreAccountRole
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.permissions.constants import BranchRelativePermissionDecision, PermissionDecisionFlag
from tests.helpers.graphql import graphql

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


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

IPAM_IP_NAMESPACE_QUERY = """
query {
  BuiltinIPNamespace {
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


QUERY_IP_PREFIX_POOL = """
query {
  CoreIPPrefixPool {
    edges {
        node {
            display_label
        }
    }
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


@dataclass
class PermissionsTestData:
    account: CoreAccount
    branch: Branch


@pytest.fixture
async def object_permissions_data(
    db: InfrahubDatabase,
    default_permission_backend: None,
    register_core_models_schema: SchemaBranch,
    default_branch: Branch,
    first_account: CoreAccount,
) -> PermissionsTestData:
    permissions = []
    for object_permission in [
        ObjectPermission(
            namespace="Builtin",
            name="*",
            action=PermissionAction.VIEW.value,
            decision=PermissionDecisionFlag.ALLOW_ALL,
        ),
        ObjectPermission(
            namespace="Builtin",
            name="*",
            action=PermissionAction.CREATE.value,
            decision=PermissionDecisionFlag.ALLOW_OTHER,
        ),
        ObjectPermission(
            namespace="Builtin",
            name="*",
            action=PermissionAction.DELETE.value,
            decision=PermissionDecisionFlag.ALLOW_OTHER,
        ),
        ObjectPermission(
            namespace="Core",
            name="*",
            action=PermissionAction.ANY.value,
            decision=PermissionDecisionFlag.ALLOW_OTHER,
        ),
        ObjectPermission(
            namespace="Core",
            name="*",
            action=PermissionAction.VIEW.value,
            decision=PermissionDecisionFlag.ALLOW_ALL,
        ),
        ObjectPermission(
            namespace="Ipam",
            name="*",
            action=PermissionAction.ANY.value,
            decision=PermissionDecisionFlag.ALLOW_OTHER,
        ),
        ObjectPermission(
            namespace="Ipam",
            name="*",
            action=PermissionAction.VIEW.value,
            decision=PermissionDecisionFlag.ALLOW_ALL,
        ),
    ]:
        obj = await Node.init(db=db, schema=InfrahubKind.OBJECTPERMISSION)
        await obj.new(
            db=db,
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

    return PermissionsTestData(account=first_account, branch=default_branch)


class TestObjectPermissions:
    async def test_first_account_tags(self, db: InfrahubDatabase, object_permissions_data: PermissionsTestData) -> None:
        """In the main branch the first account doesn't have the permission to make changes, but it has in the other branches"""
        session = AccountSession(
            authenticated=True,
            account_id=object_permissions_data.account.id,
            session_id=str(uuid4()),
            auth_type=AuthType.JWT,
        )
        gql_params = await prepare_graphql_params(
            db=db, include_mutation=True, branch=object_permissions_data.branch, account_session=session
        )

        result = await graphql(schema=gql_params.schema, source=QUERY_TAGS, context_value=gql_params.context)

        assert not result.errors
        assert result.data
        assert result.data["BuiltinTag"]["permissions"]["count"] == 1
        assert result.data["BuiltinTag"]["permissions"]["edges"][0] == {
            "node": {
                "kind": "BuiltinTag",
                "create": BranchRelativePermissionDecision.ALLOW_OTHER.name,
                "update": BranchRelativePermissionDecision.DENY.name,
                "delete": BranchRelativePermissionDecision.ALLOW_OTHER.name,
                "view": BranchRelativePermissionDecision.ALLOW.name,
            }
        }

    async def test_first_account_tags_non_main_branch(
        self, db: InfrahubDatabase, object_permissions_data: PermissionsTestData
    ) -> None:
        """In other branches the permissions for the first account is less restrictive"""
        branch2 = await create_branch(branch_name="pr-12345", db=db)
        session = AccountSession(
            authenticated=True,
            account_id=object_permissions_data.account.id,
            session_id=str(uuid4()),
            auth_type=AuthType.JWT,
        )
        gql_params = await prepare_graphql_params(db=db, include_mutation=True, branch=branch2, account_session=session)
        result = await graphql(schema=gql_params.schema, source=QUERY_TAGS, context_value=gql_params.context)
        assert not result.errors
        assert result.data
        assert result.data["BuiltinTag"]["permissions"]["count"] == 1
        assert result.data["BuiltinTag"]["permissions"]["edges"][0] == {
            "node": {
                "kind": "BuiltinTag",
                "create": BranchRelativePermissionDecision.ALLOW.name,
                "update": BranchRelativePermissionDecision.DENY.name,
                "delete": BranchRelativePermissionDecision.ALLOW.name,
                "view": BranchRelativePermissionDecision.ALLOW.name,
            }
        }

    async def test_first_account_list_permissions_for_generics(
        self, db: InfrahubDatabase, object_permissions_data: PermissionsTestData
    ) -> None:
        """In the main branch the first account doesn't have the permission to make changes"""
        session = AccountSession(
            authenticated=True,
            account_id=object_permissions_data.account.id,
            session_id=str(uuid4()),
            auth_type=AuthType.JWT,
        )
        gql_params = await prepare_graphql_params(
            db=db, include_mutation=True, branch=object_permissions_data.branch, account_session=session
        )

        result = await graphql(
            schema=gql_params.schema,
            source=IPAM_IP_NAMESPACE_QUERY,
            context_value=gql_params.context,
        )

        assert not result.errors
        assert result.data
        assert result.data["BuiltinIPNamespace"]["permissions"]["count"] == 2
        assert {
            "node": {
                "kind": "BuiltinIPNamespace",
                "create": BranchRelativePermissionDecision.ALLOW_OTHER.name,
                "update": BranchRelativePermissionDecision.DENY.name,
                "delete": BranchRelativePermissionDecision.ALLOW_OTHER.name,
                "view": BranchRelativePermissionDecision.ALLOW.name,
            }
        } in result.data["BuiltinIPNamespace"]["permissions"]["edges"]
        assert {
            "node": {
                "kind": "IpamNamespace",
                "create": BranchRelativePermissionDecision.ALLOW_OTHER.name,
                "update": BranchRelativePermissionDecision.ALLOW_OTHER.name,
                "delete": BranchRelativePermissionDecision.ALLOW_OTHER.name,
                "view": BranchRelativePermissionDecision.ALLOW.name,
            }
        } in result.data["BuiltinIPNamespace"]["permissions"]["edges"]

    async def test_first_account_ipprefix_pool(
        self, db: InfrahubDatabase, object_permissions_data: PermissionsTestData
    ) -> None:
        """In the main branch the first account doesn't have the permission to make changes, but it has in the other branches"""
        session = AccountSession(
            authenticated=True,
            account_id=object_permissions_data.account.id,
            session_id=str(uuid4()),
            auth_type=AuthType.JWT,
        )
        gql_params = await prepare_graphql_params(
            db=db, include_mutation=True, branch=object_permissions_data.branch, account_session=session
        )

        result = await graphql(schema=gql_params.schema, source=QUERY_IP_PREFIX_POOL, context_value=gql_params.context)

        assert not result.errors
        assert result.data
        assert result.data["CoreIPPrefixPool"]["permissions"]["count"] == 1
        assert result.data["CoreIPPrefixPool"]["permissions"]["edges"][0] == {
            "node": {
                "kind": "CoreIPPrefixPool",
                "create": BranchRelativePermissionDecision.ALLOW_OTHER.name,
                "update": BranchRelativePermissionDecision.ALLOW_OTHER.name,
                "delete": BranchRelativePermissionDecision.ALLOW_OTHER.name,
                "view": BranchRelativePermissionDecision.ALLOW.name,
            }
        }

    async def test_first_account_tags_non_main_branch_non_isolated(
        self, db: InfrahubDatabase, object_permissions_data: PermissionsTestData
    ) -> None:
        """In other branches the permissions for the first account should be updated if we modify the main branch"""

        branch2 = await create_branch(branch_name="pr-123abc", db=db)

        session = AccountSession(
            authenticated=True,
            account_id=object_permissions_data.account.id,
            session_id=str(uuid4()),
            auth_type=AuthType.JWT,
        )
        gql_params = await prepare_graphql_params(db=db, include_mutation=True, branch=branch2, account_session=session)

        result = await graphql(schema=gql_params.schema, source=QUERY_TAGS, context_value=gql_params.context)
        assert not result.errors
        assert result.data
        assert result.data["BuiltinTag"]["permissions"]["count"] == 1
        assert result.data["BuiltinTag"]["permissions"]["edges"][0] == {
            "node": {
                "kind": "BuiltinTag",
                "create": BranchRelativePermissionDecision.ALLOW.name,
                "update": BranchRelativePermissionDecision.DENY.name,
                "delete": BranchRelativePermissionDecision.ALLOW.name,
                "view": BranchRelativePermissionDecision.ALLOW.name,
            }
        }

        allow_modify = await Node.init(db=db, schema=InfrahubKind.OBJECTPERMISSION)
        await allow_modify.new(
            db=db,
            namespace="Builtin",
            name="Tag",
            action=PermissionAction.ANY.value,
            decision=PermissionDecisionFlag.ALLOW_OTHER,
        )
        await allow_modify.save(db=db)
        roles = await NodeManager.query(db=db, schema=CoreAccountRole, filters={"name__value": "admin"})
        assert len(roles) == 1
        admin_role = roles[0]
        await admin_role.permissions.add(data=allow_modify, db=db)
        await admin_role.save(db=db)

        session = AccountSession(
            authenticated=True,
            account_id=object_permissions_data.account.id,
            session_id=str(uuid4()),
            auth_type=AuthType.JWT,
        )
        gql_params = await prepare_graphql_params(db=db, include_mutation=True, branch=branch2, account_session=session)
        result = await graphql(schema=gql_params.schema, source=QUERY_TAGS, context_value=gql_params.context)
        assert not result.errors
        assert result.data
        assert result.data["BuiltinTag"]["permissions"]["count"] == 1
        assert result.data["BuiltinTag"]["permissions"]["edges"][0] == {
            "node": {
                "kind": "BuiltinTag",
                "create": BranchRelativePermissionDecision.ALLOW.name,
                "update": BranchRelativePermissionDecision.ALLOW.name,
                "delete": BranchRelativePermissionDecision.ALLOW.name,
                "view": BranchRelativePermissionDecision.ALLOW.name,
            }
        }


QUERY_TAGS_ATTR = """
query {
  BuiltinTag {
    count
    edges {
      node {
        name {
          value
          permissions {
            update_value
          }
        }
      }
    }
  }
}
"""


@pytest.fixture
async def attribute_permissions_data(
    db: InfrahubDatabase,
    default_permission_backend: None,
    register_core_models_schema: SchemaBranch,
    default_branch: Branch,
    first_account: CoreAccount,
) -> PermissionsTestData:
    permissions = []
    for object_permission in [
        ObjectPermission(
            namespace="Builtin",
            name="*",
            action=PermissionAction.VIEW.value,
            decision=PermissionDecisionFlag.ALLOW_ALL,
        ),
        ObjectPermission(
            namespace="Builtin",
            name="*",
            action=PermissionAction.CREATE.value,
            decision=PermissionDecisionFlag.ALLOW_ALL,
        ),
        ObjectPermission(
            namespace="Builtin",
            name="*",
            action=PermissionAction.DELETE.value,
            decision=PermissionDecisionFlag.ALLOW_ALL,
        ),
        ObjectPermission(
            namespace="Builtin",
            name="*",
            action=PermissionAction.UPDATE.value,
            decision=PermissionDecisionFlag.ALLOW_OTHER,
        ),
    ]:
        obj = await Node.init(db=db, schema=InfrahubKind.OBJECTPERMISSION)
        await obj.new(
            db=db,
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

    tag = await Node.init(db=db, schema=InfrahubKind.TAG)
    await tag.new(db=db, name="Blue", description="Blue tag")
    await tag.save(db=db)

    return PermissionsTestData(account=first_account, branch=default_branch)


class TestAttributePermissions:
    async def test_first_account_tags_main_branch(
        self, db: InfrahubDatabase, attribute_permissions_data: PermissionsTestData
    ) -> None:
        """In the main branch the first account doesn't have the permission to make changes, so attribute cannot be changed"""
        session = AccountSession(
            authenticated=True,
            account_id=attribute_permissions_data.account.id,
            session_id=str(uuid4()),
            auth_type=AuthType.JWT,
        )
        gql_params = await prepare_graphql_params(
            db=db, include_mutation=True, branch=attribute_permissions_data.branch, account_session=session
        )

        result = await graphql(schema=gql_params.schema, source=QUERY_TAGS_ATTR, context_value=gql_params.context)

        assert not result.errors
        assert result.data
        assert result.data["BuiltinTag"]["count"] == 1
        assert result.data["BuiltinTag"]["edges"][0]["node"]["name"]["permissions"] == {
            "update_value": BranchRelativePermissionDecision.ALLOW_OTHER.name
        }

    async def test_first_account_tags_non_main_branch(
        self, db: InfrahubDatabase, attribute_permissions_data: PermissionsTestData
    ) -> None:
        """In other branches the permissions for the first account is less restrictive, attribute should be updatable"""
        branch2 = await create_branch(branch_name="pr-12345", db=db)
        session = AccountSession(
            authenticated=True,
            account_id=attribute_permissions_data.account.id,
            session_id=str(uuid4()),
            auth_type=AuthType.JWT,
        )
        gql_params = await prepare_graphql_params(db=db, include_mutation=True, branch=branch2, account_session=session)

        result = await graphql(schema=gql_params.schema, source=QUERY_TAGS_ATTR, context_value=gql_params.context)

        assert not result.errors
        assert result.data
        assert result.data["BuiltinTag"]["count"] == 1
        assert result.data["BuiltinTag"]["edges"][0]["node"]["name"]["permissions"] == {
            "update_value": BranchRelativePermissionDecision.ALLOW.name
        }
