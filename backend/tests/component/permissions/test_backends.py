from infrahub.auth import AccountSession
from infrahub.core.account import ObjectPermission
from infrahub.core.branch import Branch
from infrahub.core.constants import GlobalPermissions, PermissionAction, PermissionDecision
from infrahub.database import InfrahubDatabase
from infrahub.permissions import LocalPermissionBackend


async def test_load_permissions(
    db: InfrahubDatabase, default_branch: Branch, session_admin: AccountSession, session_first_account: AccountSession
) -> None:
    backend = LocalPermissionBackend()

    permissions = await backend.load_permissions(db=db, account_session=session_admin, branch=default_branch)

    assert "global_permissions" in permissions
    assert permissions["global_permissions"][0].action == GlobalPermissions.SUPER_ADMIN.value

    assert "object_permissions" in permissions
    assert str(permissions["object_permissions"][0]) == str(
        ObjectPermission(
            namespace="*", name="*", action=PermissionAction.ANY.value, decision=PermissionDecision.ALLOW_ALL.value
        )
    )

    permissions = await backend.load_permissions(db=db, account_session=session_first_account, branch=default_branch)

    assert "global_permissions" in permissions
    assert not permissions["global_permissions"]

    assert "object_permissions" in permissions
    assert not permissions["object_permissions"]
