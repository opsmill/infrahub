from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from infrahub.permissions.constants import BranchRelativePermissionDecision


class KindPermissions(TypedDict):
    kind: str
    create: BranchRelativePermissionDecision
    delete: BranchRelativePermissionDecision
    update: BranchRelativePermissionDecision
    view: BranchRelativePermissionDecision
