"""Unit tests for the marketplace install permission helper.

These cover the exact logic that enforces FR-027 / SC-010 server-side —
independent of the FastAPI request cycle, the database, or the SDK. They
exist because the permission helper is small, critical, and easy to
regress silently; the tests should fail loudly the moment the helper
starts skipping one of the required permissions.
"""

from __future__ import annotations

from typing import Any

import pytest

from infrahub.api.marketplace import _raise_for_install_permissions
from infrahub.core import registry
from infrahub.core.account import (  # noqa: TC001  -- used at runtime by _StubPermissionManager.raise_for_permission
    GlobalPermission,
    ObjectPermission,
)
from infrahub.core.constants import GlobalPermissions
from infrahub.exceptions import PermissionDeniedError


@pytest.fixture(autouse=True)
def _default_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """`define_global_permission_from_branch` reads `registry.default_branch`.
    Stub it so tests don't need a fully-initialized registry."""
    monkeypatch.setattr(registry, "_default_branch", "main")


class _StubPermissionManager:
    """A PermissionManager double that grants exactly the action names it's configured with."""

    def __init__(self, allowed_actions: set[str]) -> None:
        self.allowed_actions = allowed_actions
        self.checked: list[str] = []

    def raise_for_permission(self, permission: GlobalPermission | ObjectPermission, message: str = "") -> None:
        action = getattr(permission, "action", None)
        self.checked.append(str(action))
        if action not in self.allowed_actions:
            raise PermissionDeniedError(message=f"denied: {action}")


def _mgr(**kwargs: Any) -> _StubPermissionManager:
    allowed = {GlobalPermissions.MANAGE_SCHEMA.value}
    if kwargs.get("manage_repositories"):
        allowed.add(GlobalPermissions.MANAGE_REPOSITORIES.value)
    if kwargs.get("edit_default_branch"):
        allowed.add(GlobalPermissions.EDIT_DEFAULT_BRANCH.value)
    return _StubPermissionManager(allowed_actions=allowed)


def test_repo_install_on_feature_branch_requires_manage_schema_and_repositories() -> None:
    pm = _mgr(manage_repositories=True)
    _raise_for_install_permissions(permission_manager=pm, target="repository", branch_name="feature")  # type: ignore[arg-type]
    assert GlobalPermissions.MANAGE_SCHEMA.value in pm.checked
    assert GlobalPermissions.MANAGE_REPOSITORIES.value in pm.checked
    assert GlobalPermissions.EDIT_DEFAULT_BRANCH.value not in pm.checked


def test_repo_install_missing_manage_repositories_raises() -> None:
    pm = _mgr()  # only MANAGE_SCHEMA
    with pytest.raises(PermissionDeniedError):
        _raise_for_install_permissions(permission_manager=pm, target="repository", branch_name="feature")  # type: ignore[arg-type]


def test_direct_install_on_feature_branch_only_requires_manage_schema() -> None:
    pm = _mgr()
    _raise_for_install_permissions(permission_manager=pm, target="direct", branch_name="feature")  # type: ignore[arg-type]
    assert pm.checked == [GlobalPermissions.MANAGE_SCHEMA.value]


def test_direct_install_missing_manage_schema_raises() -> None:
    pm = _StubPermissionManager(allowed_actions=set())
    with pytest.raises(PermissionDeniedError):
        _raise_for_install_permissions(permission_manager=pm, target="direct", branch_name="feature")  # type: ignore[arg-type]


def test_install_on_main_branch_requires_edit_default_branch() -> None:
    pm = _mgr(manage_repositories=True)
    with pytest.raises(PermissionDeniedError):
        _raise_for_install_permissions(permission_manager=pm, target="repository", branch_name="main")  # type: ignore[arg-type]


def test_install_on_main_branch_passes_when_all_permissions_granted() -> None:
    pm = _mgr(manage_repositories=True, edit_default_branch=True)
    _raise_for_install_permissions(permission_manager=pm, target="repository", branch_name="main")  # type: ignore[arg-type]
    assert GlobalPermissions.EDIT_DEFAULT_BRANCH.value in pm.checked
