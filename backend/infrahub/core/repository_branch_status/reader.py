from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.query.repository import RepositoryBranchAttributesQuery
from infrahub.core.repository_branch_status.interface import RepositoryBranchAttributesSource
from infrahub.core.repository_branch_status.models import RepositoryBranchAttributes

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence

    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


class RepositoryBranchAttributesReader(RepositoryBranchAttributesSource):
    """Read repository attribute values from the graph, resolved per branch."""

    def __init__(self, db: InfrahubDatabase, default_branch_name: str, global_branch_name: str) -> None:
        self.db = db
        self.default_branch_name = default_branch_name
        self.global_branch_name = global_branch_name

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

        Raises:
            ValueError: If the read produced two values for the same repository, branch and attribute name.

        """
        unique_branch_names = list(dict.fromkeys(branch_names))
        if not unique_branch_names or not attribute_names:
            return RepositoryBranchAttributes.from_values(values=[])

        query = await RepositoryBranchAttributesQuery.init(
            db=self.db,
            at=at,
            repository_ids=list(repository_ids),
            branch_names=unique_branch_names,
            attribute_names=list(attribute_names),
            default_branch_name=self.default_branch_name,
            global_branch_name=self.global_branch_name,
        )
        await query.execute(db=self.db)
        return RepositoryBranchAttributes.from_values(values=list(query.get_data()))
