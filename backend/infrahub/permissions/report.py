from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.permissions.resolver import PermissionResolver
    from infrahub.permissions.types import KindPermissions


__all__ = ["report_schema_permissions"]


async def report_schema_permissions(
    branch: Branch, resolver: PermissionResolver, schemas: list[MainSchemaTypes]
) -> list[KindPermissions]:
    """Build a permission report for a list of schema types.

    Uses PermissionResolver.get_branch_decision() as the single source of truth,
    ensuring the report always matches what the pipeline enforces.
    """
    global_report = resolver.build_global_report()

    return [
        {
            "kind": node.kind,
            "create": resolver.get_branch_decision(
                branch=branch, node=node, action="create", global_report=global_report
            ),
            "delete": resolver.get_branch_decision(
                branch=branch, node=node, action="delete", global_report=global_report
            ),
            "update": resolver.get_branch_decision(
                branch=branch, node=node, action="update", global_report=global_report
            ),
            "view": resolver.get_branch_decision(branch=branch, node=node, action="view", global_report=global_report),
        }
        for node in schemas
    ]
