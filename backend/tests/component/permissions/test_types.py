from dataclasses import dataclass

import pytest

from infrahub.core import registry
from infrahub.core.constants import (
    GLOBAL_BRANCH_NAME,
    GlobalPermissions,
    InfrahubKind,
    PermissionAction,
    PermissionDecision,
)
from infrahub.permissions import get_global_permission_for_kind
from infrahub.permissions.types import define_object_permission_from_branch


@pytest.mark.parametrize(
    "kinds,permission",
    [
        (
            [InfrahubKind.ACCOUNT, InfrahubKind.ACCOUNTGROUP, InfrahubKind.ACCOUNTROLE],
            GlobalPermissions.MANAGE_ACCOUNTS,
        ),
        ([InfrahubKind.GLOBALPERMISSION, InfrahubKind.OBJECTPERMISSION], GlobalPermissions.MANAGE_PERMISSIONS),
        ([InfrahubKind.REPOSITORY, InfrahubKind.READONLYREPOSITORY], GlobalPermissions.MANAGE_REPOSITORIES),
        ([InfrahubKind.TAG], None),
    ],
)
def test_get_global_permission_for_kind(
    register_core_models_schema: None, kinds: list[str], permission: GlobalPermissions
) -> None:
    for kind in kinds:
        schema = registry.schema.get(name=kind)
        assert get_global_permission_for_kind(schema=schema) == permission


@dataclass
class DefineObjectPermissionFromBranchTestCase:
    name: str
    kind: str
    action: PermissionAction
    branch_name: str
    expected_decision: PermissionDecision


DEFINE_OBJECT_PERMISSION_FROM_BRANCH_TEST_CASES: list[DefineObjectPermissionFromBranchTestCase] = [
    DefineObjectPermissionFromBranchTestCase(
        name="global_branch_returns_allow_default",
        kind=InfrahubKind.TAG,
        action=PermissionAction.CREATE,
        branch_name=GLOBAL_BRANCH_NAME,
        expected_decision=PermissionDecision.ALLOW_DEFAULT,
    ),
    DefineObjectPermissionFromBranchTestCase(
        name="default_branch_returns_allow_default",
        kind=InfrahubKind.TAG,
        action=PermissionAction.VIEW,
        branch_name="main",
        expected_decision=PermissionDecision.ALLOW_DEFAULT,
    ),
    DefineObjectPermissionFromBranchTestCase(
        name="feature_branch_returns_allow_other",
        kind=InfrahubKind.TAG,
        action=PermissionAction.UPDATE,
        branch_name="feature-branch",
        expected_decision=PermissionDecision.ALLOW_OTHER,
    ),
    DefineObjectPermissionFromBranchTestCase(
        name="develop_branch_returns_allow_other",
        kind=InfrahubKind.TAG,
        action=PermissionAction.DELETE,
        branch_name="develop",
        expected_decision=PermissionDecision.ALLOW_OTHER,
    ),
    DefineObjectPermissionFromBranchTestCase(
        name="different_kind_global_branch",
        kind=InfrahubKind.REPOSITORY,
        action=PermissionAction.CREATE,
        branch_name=GLOBAL_BRANCH_NAME,
        expected_decision=PermissionDecision.ALLOW_DEFAULT,
    ),
    DefineObjectPermissionFromBranchTestCase(
        name="different_kind_feature_branch",
        kind=InfrahubKind.REPOSITORY,
        action=PermissionAction.VIEW,
        branch_name="feature-branch",
        expected_decision=PermissionDecision.ALLOW_OTHER,
    ),
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in DEFINE_OBJECT_PERMISSION_FROM_BRANCH_TEST_CASES],
)
def test_define_object_permission_from_branch(
    register_core_models_schema: None, test_case: DefineObjectPermissionFromBranchTestCase
) -> None:
    schema = registry.schema.get(name=test_case.kind)

    result = define_object_permission_from_branch(
        schema=schema, action=test_case.action, branch_name=test_case.branch_name
    )

    assert result.namespace == schema.namespace
    assert result.name == schema.name
    assert result.action == test_case.action.value
    assert result.decision == test_case.expected_decision.value
