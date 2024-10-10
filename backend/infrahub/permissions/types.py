from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from infrahub.permissions.constants import PermissionDecisionFlag


class KindPermissions(TypedDict):
    kind: str
    create: PermissionDecisionFlag
    delete: PermissionDecisionFlag
    update: PermissionDecisionFlag
    view: PermissionDecisionFlag
