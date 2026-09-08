from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence

    from infrahub.core.repository_branch_status.models import RepositoryBranchAttributes
    from infrahub.core.timestamp import Timestamp


class RepositoryBranchAttributesSource(Protocol):
    """Source of repository attribute values resolved per branch."""

    async def read(
        self,
        repository_ids: Sequence[str],
        branch_names: Sequence[str],
        attribute_names: Collection[str],
        at: Timestamp | None = None,
    ) -> RepositoryBranchAttributes:
        """Resolve the given attributes for each repository on each branch.

        Args:
            repository_ids: UUIDs of the repository nodes to read.
            branch_names: Names of the branches to resolve the attributes on.
            attribute_names: Names of the attributes to resolve.
            at: Point in time to resolve at; the current time when omitted.

        Returns:
            A lookup holding one value per repository, branch and attribute name that resolved.

        """
        ...
