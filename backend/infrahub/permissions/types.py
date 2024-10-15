from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from infrahub.permissions.constants import PermissionDecisionFlag


class KindPermissions(TypedDict):
    kind: str
    create: PermissionDecisionFlag
    delete: PermissionDecisionFlag
    update: PermissionDecisionFlag
    view: PermissionDecisionFlag


@dataclass
class GlobalPermissionToVerify:
    name: str
    action: str
    decision: PermissionDecisionFlag


@dataclass
class ObjectPermissionToVerify:
    namespace: str
    name: str
    action: str
    decision: PermissionDecisionFlag
