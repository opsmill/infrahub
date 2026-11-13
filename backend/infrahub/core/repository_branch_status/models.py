from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Self

from infrahub.exceptions import ResourceMultipleFoundError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from infrahub.core.query.repository import RepositoryBranchAttributeValue


@dataclass(frozen=True)
class RepositoryBranchAttributes:
    """Immutable lookup of repository attribute values, addressed by repository, branch and attribute name."""

    values: Mapping[tuple[str, str], Mapping[str, RepositoryBranchAttributeValue]]
    """Attribute-name maps keyed by `(repository_id, branch_name)`."""

    @classmethod
    def from_values(cls, values: Sequence[RepositoryBranchAttributeValue]) -> Self:
        """Group resolved attribute values into a lookup.

        Args:
            values: Resolved values, at most one per repository, branch and attribute name.

        Returns:
            A lookup over the given values.

        Raises:
            ResourceMultipleFoundError: If two values share a repository, branch and attribute name,
                which means the graph holds more than one attribute of that name on that branch.

        """
        grouped: dict[tuple[str, str], dict[str, RepositoryBranchAttributeValue]] = {}
        for value in values:
            branch_values = grouped.setdefault((value.repository_id, value.branch_name), {})
            if value.attribute_name in branch_values:
                raise ResourceMultipleFoundError(
                    f"Duplicate attribute value for repository {value.repository_id!r}, "
                    f"branch {value.branch_name!r}, attribute {value.attribute_name!r}"
                )
            branch_values[value.attribute_name] = value
        return cls(
            values=MappingProxyType({key: MappingProxyType(branch_values) for key, branch_values in grouped.items()})
        )

    def get(self, repository_id: str, branch_name: str, attribute_name: str) -> RepositoryBranchAttributeValue | None:
        """Return the value for one repository, branch and attribute name, or None when nothing resolved."""
        return self.values.get((repository_id, branch_name), {}).get(attribute_name)

    def for_branch(self, repository_id: str, branch_name: str) -> dict[str, RepositoryBranchAttributeValue]:
        """Return every value that resolved for one repository on one branch, keyed by attribute name."""
        return dict(self.values.get((repository_id, branch_name), {}))
