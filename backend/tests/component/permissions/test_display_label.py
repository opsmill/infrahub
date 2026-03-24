import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import GlobalPermissions, InfrahubKind, PermissionAction, PermissionDecision
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase


@pytest.mark.parametrize(
    ("action", "decision", "expected_label"),
    [
        pytest.param(
            GlobalPermissions.MANAGE_ACCOUNTS,
            PermissionDecision.ALLOW_ALL,
            "global:manage_accounts:allow_all",
            id="manage_accounts-allow_all",
        ),
        pytest.param(
            GlobalPermissions.MERGE_BRANCH,
            PermissionDecision.DENY,
            "global:merge_branch:deny",
            id="merge_branch-deny",
        ),
        pytest.param(
            GlobalPermissions.MANAGE_SCHEMA,
            PermissionDecision.ALLOW_DEFAULT,
            "global:manage_schema:allow_default",
            id="manage_schema-allow_default",
        ),
        pytest.param(
            GlobalPermissions.MANAGE_REPOSITORIES,
            PermissionDecision.ALLOW_OTHER,
            "global:manage_repositories:allow_other",
            id="manage_repositories-allow_other",
        ),
    ],
)
async def test_global_permission_display_label(
    db: InfrahubDatabase,
    register_core_models_schema: None,
    default_branch: Branch,
    action: GlobalPermissions,
    decision: PermissionDecision,
    expected_label: str,
) -> None:
    permission = await Node.init(db=db, schema=InfrahubKind.GLOBALPERMISSION)
    await permission.new(db=db, action=action.value, decision=decision.value)
    await permission.save(db=db)

    assert await permission.get_display_label(db=db) == expected_label


@pytest.mark.parametrize(
    ("namespace", "name", "action", "decision", "expected_label"),
    [
        pytest.param(
            "Infra",
            "Device",
            PermissionAction.VIEW,
            PermissionDecision.ALLOW_ALL,
            "object:Infra:Device:view:allow_all",
            id="view-allow_all",
        ),
        pytest.param(
            "Core",
            "Account",
            PermissionAction.DELETE,
            PermissionDecision.DENY,
            "object:Core:Account:delete:deny",
            id="delete-deny",
        ),
        pytest.param(
            "*",
            "*",
            PermissionAction.ANY,
            PermissionDecision.ALLOW_ALL,
            "object:*:*:any:allow_all",
            id="any-allow_all",
        ),
        pytest.param(
            "Test",
            "Widget",
            PermissionAction.CREATE,
            PermissionDecision.ALLOW_DEFAULT,
            "object:Test:Widget:create:allow_default",
            id="create-allow_default",
        ),
        pytest.param(
            "Network",
            "Interface",
            PermissionAction.UPDATE,
            PermissionDecision.ALLOW_OTHER,
            "object:Network:Interface:update:allow_other",
            id="update-allow_other",
        ),
    ],
)
async def test_object_permission_display_label(
    db: InfrahubDatabase,
    register_core_models_schema: None,
    default_branch: Branch,
    namespace: str,
    name: str,
    action: PermissionAction,
    decision: PermissionDecision,
    expected_label: str,
) -> None:
    permission = await Node.init(db=db, schema=InfrahubKind.OBJECTPERMISSION)
    await permission.new(db=db, namespace=namespace, name=name, action=action.value, decision=decision.value)
    await permission.save(db=db)

    assert await permission.get_display_label(db=db) == expected_label
