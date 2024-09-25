from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from infrahub.core.constants import PermissionDecision


class KindPermissions(TypedDict):
    kind: str
    create: PermissionDecision
    delete: PermissionDecision
    update: PermissionDecision
    view: PermissionDecision
