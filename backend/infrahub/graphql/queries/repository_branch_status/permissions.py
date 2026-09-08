from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.account import ObjectPermission
from infrahub.exceptions import InitializationError, PermissionDeniedError
from infrahub.log import get_logger
from infrahub.permissions.constants import PermissionDecisionFlag

from .kind_dispatch import REPOSITORY_KIND_POLICIES

if TYPE_CHECKING:
    from infrahub.graphql.initialization import GraphqlContext
    from infrahub.permissions.manager import PermissionManager

    from .kind_dispatch import RepositoryKindPolicy

log = get_logger()

_CORE_NAMESPACE = "Core"


class RepositoryBranchStatusPermissionGuard:
    """View-permission guard for the cross-branch repository status read."""

    def __init__(self, context: GraphqlContext) -> None:
        self.context = context

    def ensure_any_kind_viewable(self) -> None:
        """Require view permission on at least one repository kind, before any lookup runs.

        Raises:
            PermissionDeniedError: If no repository kind is viewable, so a denial cannot reveal
                whether the requested repository exists.

        """
        permissions = [_view_permission(name=policy.permission_name) for policy in REPOSITORY_KIND_POLICIES.values()]
        active_permissions = self._active_permissions()
        for permission in permissions:
            if active_permissions.has_permission(permission=permission):
                return
        active_permissions.raise_for_permission(permission=permissions[0])

    def ensure_kind_viewable(self, policy: RepositoryKindPolicy) -> None:
        """Require view permission on the resolved repository's kind.

        Args:
            policy: Policy of the resolved repository kind.

        Raises:
            PermissionDeniedError: If the kind is not viewable across both the default branch and
                other branches.

        """
        self._active_permissions().raise_for_permission(permission=_view_permission(name=policy.permission_name))

    def _active_permissions(self) -> PermissionManager:
        try:
            return self.context.active_permissions
        except InitializationError as exc:
            # A request that carries no loaded permissions holds no grant, which is a denial.
            log.warning(
                "No permission manager was loaded for the request, "
                "treating the repository branch status read as a denial"
            )
            raise PermissionDeniedError from exc


def _view_permission(name: str) -> ObjectPermission:
    return ObjectPermission(
        namespace=_CORE_NAMESPACE,
        name=name,
        action="view",
        decision=PermissionDecisionFlag.ALLOW_ALL,
    )
