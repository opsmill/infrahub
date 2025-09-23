import pytest

from infrahub.core import core_registry
from infrahub.core.constants import GlobalPermissions, InfrahubKind
from infrahub.permissions import get_global_permission_for_kind


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
):
    for kind in kinds:
        schema = core_registry.schema.get(name=kind)
        assert get_global_permission_for_kind(schema=schema) == permission
