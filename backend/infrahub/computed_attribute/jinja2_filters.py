from __future__ import annotations

from enum import Enum

from infrahub.core.constants import PermissionAction, PermissionDecision

__all__ = ["FILTERS"]


def value_to_permission_decision_name(value: int | Enum) -> str:
    """Convert a permission decision value to its enum member name.

    Usage example: `{{ decision__value | value_to_permission_decision_name }}` will return `"ALLOW_ALL"` for value `6`.
    """
    if isinstance(value, Enum):
        value = value.value

    try:
        return PermissionDecision(value).name
    except ValueError as exc:
        msg = f"Value '{value}' not found in enum 'PermissionDecision': {exc}"
        raise ValueError(msg) from exc


def value_to_permission_action_name(value: str | Enum) -> str:
    """Convert a permission action value to its enum member name.

    Usage example: `{{ action__value | value_to_permission_action_name }}` will return `"MANAGE_ACCOUNTS"` for value `"manage_accounts"`.
    """
    if isinstance(value, Enum):
        value = value.value

    try:
        return PermissionAction(value).name
    except ValueError as exc:
        msg = f"Value '{value}' not found in enum 'PermissionAction': {exc}"
        raise ValueError(msg) from exc


FILTERS = {
    "value_to_permission_decision_name": value_to_permission_decision_name,
    "value_to_permission_action_name": value_to_permission_action_name,
}
