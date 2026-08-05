from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.branch.enums import BranchStatus
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.query.branch import (
    DeleteBranchAgnosticAttributesQuery,
    DeleteBranchAgnosticRelationshipsQuery,
    DeleteBranchEdgesQuery,
)
from infrahub.core.query.standard_node import StandardNodeDeleteQuery
from infrahub.exceptions import ValidationError
from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub.core.branch.models import Branch
    from infrahub.database import InfrahubDatabase

log = get_logger()


class BranchDeleter:
    """Remove a branch, every edge belonging to it, and the vertices that only it kept alive.

    The graph work is split into one bounded query per batch so that no single transaction has to
    hold the whole branch in memory. Each query is its own auto-commit transaction, which also means
    an interrupted delete can be resumed by running the whole thing again.
    """

    def __init__(self, db: InfrahubDatabase, batch_size: int) -> None:
        self.db = db
        self.batch_size = batch_size

    async def delete(self, branch: Branch) -> None:
        """Remove the branch's data and then the branch itself.

        Raises:
            ValidationError: When the branch is the default branch or an internal one.

        """
        if branch.is_default:
            raise ValidationError(f"Unable to delete {branch.name} it is the default branch.")
        if branch.is_global:
            raise ValidationError(f"Unable to delete {branch.name} this is an internal branch.")

        branch.status = BranchStatus.DELETING
        await branch.save(db=self.db)

        await self.delete_branch_data(branch_name=branch.name)

        query = await StandardNodeDeleteQuery.init(db=self.db, node=branch)
        await query.execute(db=self.db)

    async def delete_branch_data(self, branch_name: str) -> None:
        """Remove a branch's data without requiring the branch itself to still exist."""
        await self._delete_agnostic_peers(branch_name=branch_name)
        await self._delete_edges(branch_name=branch_name)

    async def _delete_agnostic_peers(self, branch_name: str) -> None:
        """Drop the agnostic attributes and relationships of Nodes that exist on no other branch.

        Both queries locate those Nodes through the branch's IS_PART_OF edges, so this has to
        finish before the edge deletion starts removing them. Resuming a delete that failed part
        way through this stage is safe for the same reason: no IS_PART_OF edge has been touched yet.
        """
        relationships_query = await DeleteBranchAgnosticRelationshipsQuery.init(
            db=self.db, branch_name=branch_name, batch_size=self.batch_size
        )
        await relationships_query.execute(db=self.db)

        attributes_query = await DeleteBranchAgnosticAttributesQuery.init(
            db=self.db, branch_name=branch_name, batch_size=self.batch_size
        )
        await attributes_query.execute(db=self.db)

    async def _delete_edges(self, branch_name: str) -> None:
        for edge_type in DatabaseEdgeType:
            deleted_total = 0
            while True:
                # A fresh query per batch: the stats counters accumulate per instance, so a reused
                # one would never report zero again and the loop would not end.
                query = await DeleteBranchEdgesQuery.init(
                    db=self.db, branch_name=branch_name, edge_type=edge_type, batch_size=self.batch_size
                )
                await query.execute(db=self.db)
                deleted = query.deleted_edge_count()
                if not deleted:
                    break
                deleted_total += deleted

            if deleted_total:
                # Counts every edge the batches removed, including those pulled out by the vertex
                # cleanup, so it can exceed the number of edges of this type.
                log.info(
                    "Deleted branch edges",
                    branch=branch_name,
                    edge_type=edge_type.value,
                    edges_removed=deleted_total,
                )
