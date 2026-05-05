import pytest

from infrahub.auth import AccountSession
from infrahub.core.account import GlobalPermission, ObjectPermission
from infrahub.core.branch import Branch
from infrahub.core.constants import GlobalPermissions, InfrahubKind, PermissionAction, PermissionDecision
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import PermissionDeniedError
from infrahub.permissions import PermissionManager
from infrahub.permissions.constants import PermissionDecisionFlag


async def test_has_permission_global(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    register_core_models_schema: None,
    session_admin: AccountSession,
    session_first_account: AccountSession,
    session_second_account: AccountSession,
) -> None:
    allow_default_branch_edition = GlobalPermission(
        action=GlobalPermissions.EDIT_DEFAULT_BRANCH.value, decision=PermissionDecision.ALLOW_ALL.value
    )

    role1_permissions = []
    obj = await Node.init(db=db, schema=InfrahubKind.GLOBALPERMISSION)
    await obj.new(db=db, action=allow_default_branch_edition.action, decision=allow_default_branch_edition.decision)
    await obj.save(db=db)
    role1_permissions.append(obj)

    role1 = await Node.init(db=db, schema=InfrahubKind.ACCOUNTROLE)
    await role1.new(db=db, name="anything but tags", permissions=role1_permissions)
    await role1.save(db=db)

    group1 = await Node.init(db=db, schema=InfrahubKind.ACCOUNTGROUP)
    await group1.new(db=db, name="group1", roles=[role1])
    await group1.save(db=db)

    await group1.members.add(db=db, data={"id": session_first_account.account_id})
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

    await group2.members.add(db=db, data={"id": session_second_account.account_id})
    await group2.members.save(db=db)

    permission_manager = await PermissionManager.load_for_account(
        db=db, branch=default_branch, default_branch_name=default_branch.name, account_session=session_first_account
    )
    assert permission_manager.has_permission(permission=allow_default_branch_edition)
    try:
        permission_manager.raise_for_permission(permission=allow_default_branch_edition)
    except PermissionDeniedError:
        pytest.fail("PermissionDeniedError raised unexpectedly")

    permission_manager = await PermissionManager.load_for_account(
        db=db, branch=default_branch, default_branch_name=default_branch.name, account_session=session_second_account
    )
    assert not permission_manager.has_permission(permission=allow_default_branch_edition)
    with pytest.raises(PermissionDeniedError):
        permission_manager.raise_for_permission(permission=allow_default_branch_edition)


async def test_has_permission_object(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    register_core_models_schema: None,
    session_admin: AccountSession,
    session_first_account: AccountSession,
    session_second_account: AccountSession,
) -> None:
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

    await group1.members.add(db=db, data={"id": session_first_account.account_id})
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

    await group2.members.add(db=db, data={"id": session_second_account.account_id})
    await group2.members.save(db=db)

    permission = ObjectPermission(
        namespace="Builtin",
        name="Tag",
        action=PermissionAction.CREATE.value,
        decision=PermissionDecision.ALLOW_ALL.value,
    )

    permission_manager = await PermissionManager.load_for_account(
        db=db, branch=default_branch, default_branch_name=default_branch.name, account_session=session_first_account
    )
    assert not permission_manager.has_permission(permission=permission)
    with pytest.raises(PermissionDeniedError, match=r"You do not have the following permission"):
        permission_manager.raise_for_permission(permission=permission)

    permission_manager = await PermissionManager.load_for_account(
        db=db, branch=default_branch, default_branch_name=default_branch.name, account_session=session_second_account
    )
    assert permission_manager.has_permission(permission=permission)
    try:
        permission_manager.raise_for_permission(permission=permission)
    except PermissionDeniedError:
        pytest.fail("PermissionDeniedError raised unexpectedly")


async def test_has_permissions_object(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    register_core_models_schema: None,
    session_admin: AccountSession,
    session_first_account: AccountSession,
    session_second_account: AccountSession,
) -> None:
    role1_permissions = []
    for p in [
        ObjectPermission(
            namespace="*", name="*", action=PermissionAction.ANY.value, decision=PermissionDecision.ALLOW_ALL.value
        ),
        ObjectPermission(
            namespace="Builtin", name="Tag", action=PermissionAction.ANY.value, decision=PermissionDecision.DENY.value
        ),
        ObjectPermission(
            namespace="Core",
            name="Repository",
            action=PermissionAction.ANY.value,
            decision=PermissionDecision.DENY.value,
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

    await group1.members.add(db=db, data={"id": session_first_account.account_id})
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
        ObjectPermission(
            namespace="Core",
            name="Repository",
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

    await group2.members.add(db=db, data={"id": session_second_account.account_id})
    await group2.members.save(db=db)

    permissions = [
        ObjectPermission(
            namespace="Builtin",
            name="Tag",
            action=PermissionAction.CREATE.value,
            decision=PermissionDecision.ALLOW_ALL.value,
        ),
        ObjectPermission(
            namespace="Core",
            name="Repository",
            action=PermissionAction.CREATE.value,
            decision=PermissionDecision.ALLOW_ALL.value,
        ),
    ]

    permission_manager = await PermissionManager.load_for_account(
        db=db, branch=default_branch, default_branch_name=default_branch.name, account_session=session_first_account
    )
    assert not permission_manager.has_permissions(permissions=permissions)
    with pytest.raises(PermissionDeniedError, match=r"You do not have one of the following permissions"):
        permission_manager.raise_for_permissions(permissions=permissions)

    permission_manager = await PermissionManager.load_for_account(
        db=db, branch=default_branch, default_branch_name=default_branch.name, account_session=session_second_account
    )
    assert permission_manager.has_permissions(permissions=permissions)
    try:
        permission_manager.raise_for_permissions(permissions=permissions)
    except PermissionDeniedError:
        pytest.fail("PermissionDeniedError raised unexpectedly")


async def test_report_permission_object(
    db: InfrahubDatabase,
    default_branch: Branch,
    default_permission_backend: None,
    register_core_models_schema: None,
    session_admin: AccountSession,
    session_first_account: AccountSession,
    session_second_account: AccountSession,
) -> None:
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

    await group1.members.add(db=db, data={"id": session_first_account.account_id})
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

    await group2.members.add(db=db, data={"id": session_second_account.account_id})
    await group2.members.save(db=db)

    permission_manager = await PermissionManager.load_for_account(
        db=db, branch=default_branch, default_branch_name=default_branch.name, account_session=session_first_account
    )
    assert (
        permission_manager.report_object_permission(namespace="Builtin", name="Tag", action="create")
        == PermissionDecisionFlag.DENY
    )
    assert (
        permission_manager.report_object_permission(namespace="Core", name="Account", action="view")
        == PermissionDecisionFlag.ALLOW_ALL
    )

    permission_manager = await PermissionManager.load_for_account(
        db=db, branch=default_branch, default_branch_name=default_branch.name, account_session=session_second_account
    )
    assert (
        permission_manager.report_object_permission(namespace="Builtin", name="Tag", action="create")
        == PermissionDecisionFlag.ALLOW_ALL
    )
    assert (
        permission_manager.report_object_permission(namespace="Core", name="Account", action="view")
        == PermissionDecisionFlag.DENY
    )
