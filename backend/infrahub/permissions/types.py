from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from infrahub.permissions.constants import BranchAwarePermissionDecision


class KindPermissions(TypedDict):
    kind: str
    create: BranchAwarePermissionDecision
    delete: BranchAwarePermissionDecision
    update: BranchAwarePermissionDecision
    view: BranchAwarePermissionDecision
