from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import ValidationError

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.registry import Registry


class BranchQueryTimeValidator:
    def __init__(self, registry: Registry) -> None:
        self._registry = registry

    def validate(self, branch: Branch, at: Timestamp) -> None:
        """Validate that `at` falls within the branch's effective lifetime.

        Raises:
            ValidationError: When `at` is earlier than the branch's effective creation time.

        """
        if branch.is_default or branch.is_global or branch.origin_branch == branch.name:
            boundary_branch_name = branch.name
            boundary_created_at = branch.get_created_at()
        else:
            origin = self._registry.get_branch_from_registry(branch=branch.origin_branch)
            boundary_branch_name = origin.name
            boundary_created_at = origin.get_created_at()

        if at < Timestamp(boundary_created_at):
            raise ValidationError(
                f"Requested time '{at.to_string()}' is before "
                f"branch '{boundary_branch_name}' was created at '{boundary_created_at}'."
            )
