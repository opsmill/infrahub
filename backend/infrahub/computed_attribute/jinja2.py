from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from infrahub_sdk.template import Jinja2Template

from infrahub.core.constants import PermissionAction, PermissionDecision

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

__all__ = ["InfrahubJinja2Template"]


def _value_to_permission_decision_name(value: int | str | Enum) -> str:
    """Convert a permission decision value to its enum member name.

    Usage example: `{{ decision__value | value_to_permission_decision_name }}` will return `"ALLOW_ALL"` for value `6`.
    """
    raw_value = value.value if isinstance(value, Enum) else value

    try:
        int_value = int(raw_value)
    except ValueError as exc:
        msg = f"Value '{value}' is not a valid int for permission decision value: {exc}"
        raise ValueError(msg) from exc

    try:
        return PermissionDecision(int_value).name
    except ValueError as exc:
        msg = f"Value '{int_value}' not found in enum 'PermissionDecision': {exc}"
        raise ValueError(msg) from exc


def _value_to_permission_action_name(value: str | Enum) -> str:
    """Convert a permission action value to its enum member name.

    Usage examples:
    - `{{ action__value | value_to_permission_action_name }}` will return `"CREATE"` for value `"create"` for object permissions.
    - `{{ action__value | value_to_permission_action_name }}` will return `"SUPER_ADMIN"` for value `"super_admin"` for global permissions.
    """
    if isinstance(value, Enum):
        value = value.value

    try:
        return PermissionAction(str(value)).name
    except ValueError as exc:
        msg = f"Value '{value}' not found in enum 'PermissionAction': {exc}"
        raise ValueError(msg) from exc


FILTERS: dict[str, Callable[..., str]] = {
    "value_to_permission_decision_name": _value_to_permission_decision_name,
    "value_to_permission_action_name": _value_to_permission_action_name,
}


class InfrahubJinja2Template(Jinja2Template):
    """Extend SDK's `Jinja2Template` with Infrahub server-specific filters pre-configured."""

    def __init__(
        self,
        template: str | Path,
        template_directory: Path | None = None,
        filters: dict[str, Callable[..., str]] | None = None,
    ) -> None:
        super().__init__(
            template=template, template_directory=template_directory, filters={**FILTERS, **(filters or {})}
        )
