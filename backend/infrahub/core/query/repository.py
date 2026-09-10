from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RepositoryBranchAttributeValue:
    """One repository attribute value as it resolves on one branch."""

    repository_id: str
    """UUID of the repository node."""

    branch_name: str
    """Name of the branch the value was resolved for."""

    attribute_name: str
    """Name of the attribute, e.g. `commit`."""

    attribute_id: str
    """UUID of the attribute node."""

    value: str | None
    """Value carried by the winning value edge."""

    own_value: bool
    """True when the winning value edge lives on `branch_name` itself rather than being inherited."""

    updated_at: str | None
    """Time the winning value edge was created."""
