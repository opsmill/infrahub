from infrahub.core.account import GlobalPermission, ObjectPermission
from infrahub.core.branch import Branch
from infrahub.core.constants import GlobalPermissions, InfrahubKind, PermissionAction, PermissionDecision
from infrahub.core.node import Node
from infrahub.core.protocols import CoreAccount
from infrahub.database import InfrahubDatabase
from infrahub.permissions import LocalPermissionBackend
from infrahub.permissions.constants import PermissionDecisionFlag


async def test_load_permissions(db: InfrahubDatabase, default_branch: Branch, create_test_admin, first_account):
    backend = LocalPermissionBackend()

    permissions = await backend.load_permissions(db=db, account_id=create_test_admin.id, branch=default_branch)

    assert "global_permissions" in permissions
    assert permissions["global_permissions"][0].action == GlobalPermissions.SUPER_ADMIN.value

    assert "object_permissions" in permissions
    assert str(permissions["object_permissions"][0]) == str(
        ObjectPermission(
            namespace="*", name="*", action=PermissionAction.ANY.value, decision=PermissionDecision.ALLOW_ALL.value
        )
    )

    permissions = await backend.load_permissions(db=db, account_id=first_account.id, branch=default_branch)

    assert "global_permissions" in permissions
    assert not permissions["global_permissions"]

    assert "object_permissions" in permissions
    assert not permissions["object_permissions"]


async def test_has_permission_global(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    create_test_admin: CoreAccount,
    first_account: CoreAccount,
    second_account: CoreAccount,
):
    backend = LocalPermissionBackend()

    allow_default_branch_edition = GlobalPermission(
        action=GlobalPermissions.EDIT_DEFAULT_BRANCH.value, decision=PermissionDecision.ALLOW_ALL.value
    )

    role1_permissions = []
    obj = await Node.init(db=db, schema=InfrahubKind.GLOBALPERMISSION)
    await obj.new(
        db=db,
        name=allow_default_branch_edition.name,
        action=allow_default_branch_edition.action,
        decision=allow_default_branch_edition.decision,
    )
    await obj.save(db=db)
    role1_permissions.append(obj)

    role1 = await Node.init(db=db, schema=InfrahubKind.ACCOUNTROLE)
    await role1.new(db=db, name="anything but tags", permissions=role1_permissions)
    await role1.save(db=db)

    group1 = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
    await group1.new(db=db, name="group1", roles=[role1])
    await group1.save(db=db)

    await group1.members.add(db=db, data={"id": first_account.id})
    await group1.members.save(db=db)

    role2_permissions = []
    for p in [
        allow_default_branch_edition,
        GlobalPermission(action=GlobalPermissions.EDIT_DEFAULT_BRANCH.value, decision=PermissionDecision.DENY.value),
    ]:
        obj = await Node.init(db=db, schema=InfrahubKind.GLOBALPERMISSION)
        await obj.new(db=db, action=p.action, decision=p.decision)
        await obj.save(db=db)
        role2_permissions.append(obj)

    role2 = await Node.init(db=db, schema=InfrahubKind.ACCOUNTROLE)
    await role2.new(db=db, name="only tags", permissions=role2_permissions)
    await role2.save(db=db)

    group2 = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
    await group2.new(db=db, name="group2", roles=[role2])
    await group2.save(db=db)

    await group2.members.add(db=db, data={"id": second_account.id})
    await group2.members.save(db=db)

    assert await backend.has_permission(
        db=db, account_id=first_account.id, permission=allow_default_branch_edition, branch=default_branch
    )
    assert not await backend.has_permission(
        db=db, account_id=second_account.id, permission=allow_default_branch_edition, branch=default_branch
    )


async def test_has_permission_object(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    create_test_admin: CoreAccount,
    first_account: CoreAccount,
    second_account: CoreAccount,
):
    backend = LocalPermissionBackend()

    role1_permissions = []
    for p in [
        ObjectPermission(
            namespace="*", name="*", action=PermissionAction.ANY.value, decision=PermissionDecision.ALLOW_ALL.value
        ),
        ObjectPermission(
            namespace="Builtin", name="Tag", action=PermissionAction.ANY.value, decision=PermissionDecision.DENY.value
        ),
    ]:
        obj = await Node.init(db=db, schema=InfrahubKind.OBJECTPERMISSION)
        await obj.new(db=db, namespace=p.namespace, name=p.name, action=p.action, decision=p.decision)
        await obj.save(db=db)
        role1_permissions.append(obj)

    role1 = await Node.init(db=db, schema=InfrahubKind.ACCOUNTROLE)
    await role1.new(db=db, name="anything but tags", permissions=role1_permissions)
    await role1.save(db=db)

    group1 = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
    await group1.new(db=db, name="group1", roles=[role1])
    await group1.save(db=db)

    await group1.members.add(db=db, data={"id": first_account.id})
    await group1.members.save(db=db)

    role2_permissions = []
    for p in [
        ObjectPermission(
            namespace="*", name="*", action=PermissionAction.ANY.value, decision=PermissionDecision.DENY.value
        ),
        ObjectPermission(
            namespace="Builtin",
            name="Tag",
            action=PermissionAction.ANY.value,
            decision=PermissionDecision.ALLOW_ALL.value,
        ),
    ]:
        obj = await Node.init(db=db, schema=InfrahubKind.OBJECTPERMISSION)
        await obj.new(db=db, namespace=p.namespace, name=p.name, action=p.action, decision=p.decision)
        await obj.save(db=db)
        role2_permissions.append(obj)

    role2 = await Node.init(db=db, schema=InfrahubKind.ACCOUNTROLE)
    await role2.new(db=db, name="only tags", permissions=role2_permissions)
    await role2.save(db=db)

    group2 = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
    await group2.new(db=db, name="group2", roles=[role2])
    await group2.save(db=db)

    await group2.members.add(db=db, data={"id": second_account.id})
    await group2.members.save(db=db)

    permission = ObjectPermission(
        namespace="Builtin",
        name="Tag",
        action=PermissionAction.CREATE.value,
        decision=PermissionDecision.ALLOW_ALL.value,
    )
    assert not await backend.has_permission(
        db=db, account_id=first_account.id, permission=permission, branch=default_branch
    )
    assert await backend.has_permission(
        db=db, account_id=second_account.id, permission=permission, branch=default_branch
    )


async def test_report_permission_object(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    create_test_admin: CoreAccount,
    first_account: CoreAccount,
    second_account: CoreAccount,
):
    backend = LocalPermissionBackend()

    role1_permissions = []
    for p in [
        ObjectPermission(
            namespace="*", name="*", action=PermissionAction.ANY.value, decision=PermissionDecision.ALLOW_ALL.value
        ),
        ObjectPermission(
            namespace="Builtin", name="Tag", action=PermissionAction.ANY.value, decision=PermissionDecision.DENY.value
        ),
    ]:
        obj = await Node.init(db=db, schema=InfrahubKind.OBJECTPERMISSION)
        await obj.new(db=db, namespace=p.namespace, name=p.name, action=p.action, decision=p.decision)
        await obj.save(db=db)
        role1_permissions.append(obj)

    role1 = await Node.init(db=db, schema=InfrahubKind.ACCOUNTROLE)
    await role1.new(db=db, name="anything but tags", permissions=role1_permissions)
    await role1.save(db=db)

    group1 = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
    await group1.new(db=db, name="group1", roles=[role1])
    await group1.save(db=db)

    await group1.members.add(db=db, data={"id": first_account.id})
    await group1.members.save(db=db)

    role2_permissions = []
    for p in [
        ObjectPermission(
            namespace="*", name="*", action=PermissionAction.ANY.value, decision=PermissionDecision.DENY.value
        ),
        ObjectPermission(
            namespace="Builtin",
            name="Tag",
            action=PermissionAction.ANY.value,
            decision=PermissionDecision.ALLOW_ALL.value,
        ),
    ]:
        obj = await Node.init(db=db, schema=InfrahubKind.OBJECTPERMISSION)
        await obj.new(db=db, namespace=p.namespace, name=p.name, action=p.action, decision=p.decision)
        await obj.save(db=db)
        role2_permissions.append(obj)

    role2 = await Node.init(db=db, schema=InfrahubKind.ACCOUNTROLE)
    await role2.new(db=db, name="only tags", permissions=role2_permissions)
    await role2.save(db=db)

    group2 = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
    await group2.new(db=db, name="group2", roles=[role2])
    await group2.save(db=db)

    await group2.members.add(db=db, data={"id": second_account.id})
    await group2.members.save(db=db)

    first_permissions = await backend.load_permissions(db=db, account_id=first_account.id, branch=default_branch)

    assert (
        backend.report_object_permission(
            permissions=first_permissions["object_permissions"], namespace="Builtin", name="Tag", action="create"
        )
        == PermissionDecisionFlag.DENY
    )
    assert (
        backend.report_object_permission(
            permissions=first_permissions["object_permissions"], namespace="Core", name="Account", action="view"
        )
        == PermissionDecisionFlag.ALLOW_ALL
    )

    second_permissions = await backend.load_permissions(db=db, account_id=second_account.id, branch=default_branch)

    assert (
        backend.report_object_permission(
            permissions=second_permissions["object_permissions"], namespace="Builtin", name="Tag", action="create"
        )
        == PermissionDecisionFlag.ALLOW_ALL
    )
    assert (
        backend.report_object_permission(
            permissions=second_permissions["object_permissions"], namespace="Core", name="Account", action="view"
        )
        == PermissionDecisionFlag.DENY
    )
