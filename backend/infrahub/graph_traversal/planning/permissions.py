from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.account import ObjectPermission
from infrahub.permissions.constants import PermissionDecisionFlag

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.permissions.resolver import PermissionResolver


class KindPermissionCache:
    """Per-request memoized view-permission decisions, keyed by kind name.

    Constructed and owned by `SchemaPlanner.initialize()`; not part of the planner's
    public surface. One `ObjectPermission` is built per distinct kind queried, then
    delegated to the resolver. Subsequent lookups for the same kind hit the in-memory
    dict.
    """

    __slots__ = ("_branch", "_decisions", "_resolver", "_schema_branch")

    def __init__(
        self,
        *,
        resolver: PermissionResolver,
        branch: Branch,
        schema_branch: SchemaBranch,
    ) -> None:
        self._resolver = resolver
        self._branch = branch
        self._schema_branch = schema_branch
        self._decisions: dict[str, bool] = {}

    def can_view(self, kind: str) -> bool:
        decision = self._decisions.get(kind)
        if decision is not None:
            return decision

        namespace = self._schema_branch.get(name=kind, duplicate=False).namespace
        decision_flag = (
            PermissionDecisionFlag.ALLOW_DEFAULT if self._branch.is_default else PermissionDecisionFlag.ALLOW_OTHER
        )
        permission = ObjectPermission(
            namespace=namespace,
            name=kind,
            action="view",
            decision=decision_flag.value,
        )
        result = self._resolver.has_permission(permission=permission)
        self._decisions[kind] = result
        return result
