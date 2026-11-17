from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.account import fetch_permissions, fetch_role_permissions
from infrahub.core.constants import GlobalPermissions, InfrahubKind, PermissionDecision
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


async def _grant_edit_default_branch(db: InfrahubDatabase, account: Node) -> tuple[Node, Node, Node]:
    permission = await Node.init(db=db, schema=InfrahubKind.GLOBALPERMISSION)
    await permission.new(
        db=db, action=GlobalPermissions.EDIT_DEFAULT_BRANCH.value, decision=PermissionDecision.ALLOW_ALL.value
    )
    await permission.save(db=db)

    role = await Node.init(db=db, schema=InfrahubKind.ACCOUNTROLE)
    await role.new(db=db, name="editors", permissions=[permission])
    await role.save(db=db)

    group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
    await group.new(db=db, name="editors", roles=[role])
    await group.save(db=db)

    await group.members.add(db=db, data={"id": account.id})
    await group.members.save(db=db)
    return permission, role, group


async def _global_actions(db: InfrahubDatabase, account: Node, branch: Branch) -> set[str]:
    permissions = await fetch_permissions(db=db, account_id=account.id, branch=branch)
    return {permission.action for permission in permissions["global_permissions"]}


async def _role_global_actions(db: InfrahubDatabase, role: Node, branch: Branch) -> set[str]:
    permissions = await fetch_role_permissions(db=db, role_id=role.id, branch=branch)
    return {permission.action for permission in permissions["global_permissions"]}


class TestGlobalPermissionsReadDefaultBranch:
    async def test_membership_removed_on_branch_keeps_permission_on_default(
        self, db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None, first_account: Node
    ) -> None:
        _, _, group = await _grant_edit_default_branch(db=db, account=first_account)
        branch = await create_branch(db=db, branch_name="drop-member")

        group_on_branch = await NodeManager.get_one(db=db, id=group.id, branch=branch, raise_on_error=True)
        await group_on_branch.members.update(db=db, data=[])
        await group_on_branch.members.save(db=db)

        assert await _global_actions(db=db, account=first_account, branch=default_branch) == {
            GlobalPermissions.EDIT_DEFAULT_BRANCH.value
        }

    async def test_role_removed_from_group_on_branch_keeps_permission_on_default(
        self, db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None, first_account: Node
    ) -> None:
        _, _, group = await _grant_edit_default_branch(db=db, account=first_account)
        branch = await create_branch(db=db, branch_name="drop-role")

        group_on_branch = await NodeManager.get_one(db=db, id=group.id, branch=branch, raise_on_error=True)
        await group_on_branch.roles.update(db=db, data=[])
        await group_on_branch.roles.save(db=db)

        assert await _global_actions(db=db, account=first_account, branch=default_branch) == {
            GlobalPermissions.EDIT_DEFAULT_BRANCH.value
        }

    async def test_role_deleted_on_branch_keeps_permission_on_default(
        self, db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None, first_account: Node
    ) -> None:
        _, role, _ = await _grant_edit_default_branch(db=db, account=first_account)
        branch = await create_branch(db=db, branch_name="delete-role")

        role_on_branch = await NodeManager.get_one(db=db, id=role.id, branch=branch, raise_on_error=True)
        await role_on_branch.delete(db=db)

        assert await _global_actions(db=db, account=first_account, branch=default_branch) == {
            GlobalPermissions.EDIT_DEFAULT_BRANCH.value
        }

    async def test_permission_removed_from_role_on_branch_keeps_permission_on_default(
        self, db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None, first_account: Node
    ) -> None:
        _, role, _ = await _grant_edit_default_branch(db=db, account=first_account)
        branch = await create_branch(db=db, branch_name="drop-permission")

        role_on_branch = await NodeManager.get_one(db=db, id=role.id, branch=branch, raise_on_error=True)
        await role_on_branch.permissions.update(db=db, data=[])
        await role_on_branch.permissions.save(db=db)

        assert await _global_actions(db=db, account=first_account, branch=default_branch) == {
            GlobalPermissions.EDIT_DEFAULT_BRANCH.value
        }
        assert await _role_global_actions(db=db, role=role, branch=default_branch) == {
            GlobalPermissions.EDIT_DEFAULT_BRANCH.value
        }

    async def test_membership_added_on_branch_does_not_grant_permission(
        self, db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None, first_account: Node
    ) -> None:
        permission = await Node.init(db=db, schema=InfrahubKind.GLOBALPERMISSION)
        await permission.new(
            db=db, action=GlobalPermissions.SUPER_ADMIN.value, decision=PermissionDecision.ALLOW_ALL.value
        )
        await permission.save(db=db)
        role = await Node.init(db=db, schema=InfrahubKind.ACCOUNTROLE)
        await role.new(db=db, name="admins", permissions=[permission])
        await role.save(db=db)
        group = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
        await group.new(db=db, name="admins", roles=[role])
        await group.save(db=db)

        branch = await create_branch(db=db, branch_name="add-member")
        group_on_branch = await NodeManager.get_one(db=db, id=group.id, branch=branch, raise_on_error=True)
        await group_on_branch.members.add(db=db, data={"id": first_account.id})
        await group_on_branch.members.save(db=db)

        assert await _global_actions(db=db, account=first_account, branch=default_branch) == set()
        assert await _global_actions(db=db, account=first_account, branch=branch) == set()

    async def test_membership_removed_on_default_after_branch(
        self, db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None, first_account: Node
    ) -> None:
        _, _, group = await _grant_edit_default_branch(db=db, account=first_account)
        branch = await create_branch(db=db, branch_name="keeps-member")

        group_on_default = await NodeManager.get_one(db=db, id=group.id, branch=default_branch, raise_on_error=True)
        await group_on_default.members.update(db=db, data=[])
        await group_on_default.members.save(db=db)

        assert await _global_actions(db=db, account=first_account, branch=default_branch) == set()
        assert await _global_actions(db=db, account=first_account, branch=branch) == set()

    async def test_permission_removed_from_role_on_branch_keeps_role_permission_on_default(
        self, db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None, first_account: Node
    ) -> None:
        _, role, _ = await _grant_edit_default_branch(db=db, account=first_account)
        branch = await create_branch(db=db, branch_name="drop-role-permission")

        role_on_branch = await NodeManager.get_one(db=db, id=role.id, branch=branch, raise_on_error=True)
        await role_on_branch.permissions.update(db=db, data=[])
        await role_on_branch.permissions.save(db=db)

        assert await _role_global_actions(db=db, role=role, branch=default_branch) == {
            GlobalPermissions.EDIT_DEFAULT_BRANCH.value
        }

    async def test_global_permission_deleted_on_default(
        self, db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None, first_account: Node
    ) -> None:
        permission, _, _ = await _grant_edit_default_branch(db=db, account=first_account)
        await create_branch(db=db, branch_name="before-permission-delete")

        permission_on_default = await NodeManager.get_one(
            db=db, id=permission.id, branch=default_branch, raise_on_error=True
        )
        await permission_on_default.delete(db=db)

        assert await _global_actions(db=db, account=first_account, branch=default_branch) == set()

    async def test_account_group_deleted_on_default(
        self, db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None, first_account: Node
    ) -> None:
        _, _, group = await _grant_edit_default_branch(db=db, account=first_account)

        group_on_default = await NodeManager.get_one(db=db, id=group.id, branch=default_branch, raise_on_error=True)
        await group_on_default.delete(db=db)

        assert await _global_actions(db=db, account=first_account, branch=default_branch) == set()

    async def test_global_permission_linked_on_branch_does_not_grant_permission(
        self, db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None, first_account: Node
    ) -> None:
        _, role, _ = await _grant_edit_default_branch(db=db, account=first_account)
        extra = await Node.init(db=db, schema=InfrahubKind.GLOBALPERMISSION)
        await extra.new(db=db, action=GlobalPermissions.SUPER_ADMIN.value, decision=PermissionDecision.ALLOW_ALL.value)
        await extra.save(db=db)

        branch = await create_branch(db=db, branch_name="link-permission")
        role_on_branch = await NodeManager.get_one(db=db, id=role.id, branch=branch, raise_on_error=True)
        await role_on_branch.permissions.add(db=db, data={"id": extra.id})
        await role_on_branch.permissions.save(db=db)

        assert await _global_actions(db=db, account=first_account, branch=default_branch) == {
            GlobalPermissions.EDIT_DEFAULT_BRANCH.value
        }
        assert await _global_actions(db=db, account=first_account, branch=branch) == {
            GlobalPermissions.EDIT_DEFAULT_BRANCH.value
        }
