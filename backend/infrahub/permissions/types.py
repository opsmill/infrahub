from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from infrahub.core.constants import GlobalPermissions, InfrahubKind
from infrahub.core.schema import NodeSchema

if TYPE_CHECKING:
    from infrahub.core.account import GlobalPermission, ObjectPermission
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.permissions.constants import BranchRelativePermissionDecision


class AssignedPermissions(TypedDict):
    global_permissions: list[GlobalPermission]
    object_permissions: list[ObjectPermission]


class KindPermissions(TypedDict):
    kind: str
    create: BranchRelativePermissionDecision
    delete: BranchRelativePermissionDecision
    update: BranchRelativePermissionDecision
    view: BranchRelativePermissionDecision


def get_global_permission_for_kind(schema: MainSchemaTypes) -> GlobalPermissions | None:
    kind_permission_map = {
        InfrahubKind.GENERICACCOUNT: GlobalPermissions.MANAGE_ACCOUNTS,
        InfrahubKind.ACCOUNTGROUP: GlobalPermissions.MANAGE_ACCOUNTS,
        InfrahubKind.ACCOUNTROLE: GlobalPermissions.MANAGE_ACCOUNTS,
        InfrahubKind.BASEPERMISSION: GlobalPermissions.MANAGE_PERMISSIONS,
        InfrahubKind.GENERICREPOSITORY: GlobalPermissions.MANAGE_REPOSITORIES,
    }

    if schema.kind in kind_permission_map:
        return kind_permission_map[schema.kind]

    if isinstance(schema, NodeSchema):
        for base in schema.inherit_from:
            try:
                return kind_permission_map[base]
            except KeyError:
                continue

    return None
