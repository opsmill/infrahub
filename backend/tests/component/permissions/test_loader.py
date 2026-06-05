from infrahub.auth.session import AccountSession
from infrahub.core import registry
from infrahub.core.account import ObjectPermission
from infrahub.core.branch import Branch
from infrahub.core.constants import GlobalPermissions, PermissionAction, PermissionDecision
from infrahub.database import InfrahubDatabase
from infrahub.permissions import AssignedPermissions, PermissionBackend, PermissionLoader
from infrahub.permissions.constants import PermissionDecisionFlag


class DummyBackendAllow(PermissionBackend):
    async def load_permissions(
        self, db: InfrahubDatabase, branch: Branch, account_session: AccountSession
    ) -> AssignedPermissions:
        return {
            "global_permissions": [],
            "object_permissions": [ObjectPermission("*", "*", "*", PermissionDecisionFlag.ALLOW_ALL.value)],
        }


class DummyBackendDeny(PermissionBackend):
    async def load_permissions(
        self, db: InfrahubDatabase, branch: Branch, account_session: AccountSession
    ) -> AssignedPermissions:
        return {
            "global_permissions": [],
            "object_permissions": [ObjectPermission("Ipam", "*", "*", PermissionDecisionFlag.DENY.value)],
        }


async def test_load_permissions(
    db: InfrahubDatabase,
    default_permission_backend: None,
    default_branch: Branch,
    session_admin: AccountSession,
    session_first_account: AccountSession,
) -> None:
    loader = PermissionLoader(account_session=session_admin)
    permissions = await loader.load(db=db, branch=default_branch)

    assert "global_permissions" in permissions
    assert permissions["global_permissions"][0].action == GlobalPermissions.SUPER_ADMIN.value

    assert "object_permissions" in permissions
    assert str(permissions["object_permissions"][0]) == str(
        ObjectPermission(
            namespace="*", name="*", action=PermissionAction.ANY.value, decision=PermissionDecision.ALLOW_ALL.value
        )
    )

    loader = PermissionLoader(account_session=session_first_account)
    permissions = await loader.load(db=db, branch=default_branch)

    assert "global_permissions" in permissions
    assert not permissions["global_permissions"]

    assert "object_permissions" in permissions
    assert not permissions["object_permissions"]


async def test_load_permissions_multiple_backends(
    db: InfrahubDatabase, default_branch: Branch, session_first_account: AccountSession
) -> None:
    registry.permission_backends = [DummyBackendAllow(), DummyBackendDeny()]

    loader = PermissionLoader(account_session=session_first_account)
    permissions = await loader.load(db=db, branch=default_branch)

    assert "global_permissions" in permissions
    assert not permissions["global_permissions"]

    assert "object_permissions" in permissions
    assert len(permissions["object_permissions"]) == 2
