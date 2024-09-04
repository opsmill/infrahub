from infrahub.core.account import GlobalPermission
from infrahub.core.constants import GlobalPermissions
from infrahub.database import InfrahubDatabase
from infrahub.permissions import LocalPermissionBackend


async def test_load_permissions(db: InfrahubDatabase, create_test_admin, first_account):
    backend = LocalPermissionBackend()

    permissions = await backend.load_permissions(db=db, account_id=create_test_admin.id)
    assert "global_permissions" in permissions
    assert permissions["global_permissions"][0].action == GlobalPermissions.EDIT_DEFAULT_BRANCH.value

    permissions = await backend.load_permissions(db=db, account_id=first_account.id)
    assert "global_permissions" in permissions
    assert not permissions["global_permissions"]


async def test_has_permissions(db: InfrahubDatabase, create_test_admin, first_account):
    backend = LocalPermissionBackend()
    permission = GlobalPermission(id="", action=GlobalPermissions.EDIT_DEFAULT_BRANCH.value, name="Edit default branch")

    assert await backend.has_permission(db=db, account_id=create_test_admin.id, permission=str(permission))
    assert not await backend.has_permission(db=db, account_id=first_account.id, permission=str(permission))
