from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

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

# The agnostic cleanup batches Nodes, and each one can drag an unbounded number of peer vertices
# into the transaction with it, so its batch is capped low.
MAX_AGNOSTIC_PEER_BATCH_SIZE = 500


@dataclass(frozen=True)
class BranchDeleteResult:
    """What a delete attempt actually did.

    `branch_deleted` is false when the branch had already been removed by the time this attempt got
    to it, which is how a caller knows not to repeat the work that follows a delete.
    """

    branch_deleted: bool
    edges_removed: int


class BranchDataDeleterInterface(Protocol):
    """The database side of a branch delete."""

    async def delete(self, branch: Branch) -> BranchDeleteResult: ...


class LoggerInterface(Protocol):
    """Just enough of a logger for progress reporting."""

    def info(self, message: str, /) -> Any: ...


class BranchDataDeleter:
    """Remove a branch, every edge belonging to it, and the vertices that only it kept alive.

    The graph work is split into one bounded query per batch so that no single transaction has to
    hold the whole branch in memory. Each query is its own auto-commit transaction, which also means
    an interrupted delete can be resumed by running the whole thing again.
    """

    def __init__(self, db: InfrahubDatabase, batch_size: int, log: LoggerInterface | None = None) -> None:
        self.db = db
        self.batch_size = batch_size
        self.log = log or get_logger()

    async def delete(self, branch: Branch) -> BranchDeleteResult:
        """Remove the branch's data and then the branch itself.

        Returns whether the Branch object was actually deleted in case multiple processes try to
        delete concurrently so the caller can know which delete really succeeded.

        Raises:
            ValidationError: When the branch is the default branch or an internal one.

        """
        if branch.is_default:
            raise ValidationError(f"Unable to delete {branch.name} it is the default branch.")
        if branch.is_global:
            raise ValidationError(f"Unable to delete {branch.name} this is an internal branch.")

        if branch.status != BranchStatus.DELETING:
            branch.status = BranchStatus.DELETING
            await branch.save(db=self.db)

        edges_removed = await self.delete_branch_data(branch_name=branch.name)

        query = await StandardNodeDeleteQuery.init(db=self.db, node=branch)
        await query.execute(db=self.db)
        branch_deleted = query.stats.get_counter("nodes_deleted") > 0

        return BranchDeleteResult(branch_deleted=branch_deleted, edges_removed=edges_removed)

    async def delete_branch_data(self, branch_name: str) -> int:
        """Remove a branch's data without requiring the branch itself to still exist.

        Returns the number of edges removed, so a caller whose own logging is the only thing the
        operator can see is able to report progress.
        """
        agnostic_edges_count = await self._delete_agnostic_peers(branch_name=branch_name)
        branch_edges_count = await self._delete_edges(branch_name=branch_name)
        return agnostic_edges_count + branch_edges_count

    async def _delete_agnostic_peers(self, branch_name: str) -> int:
        """Drop the agnostic attributes and relationships of Nodes that exist on no other branch.

        Both queries locate those Nodes through the branch's IS_PART_OF edges, so this has to
        finish before the edge deletion starts removing them. Resuming a delete that failed part
        way through this stage is safe for the same reason: no IS_PART_OF edge has been touched yet.

        Returns the number of edges removed, which is every edge of the peers detached here, not
        only the agnostic ones that led to them.
        """
        batch_size = min(self.batch_size, MAX_AGNOSTIC_PEER_BATCH_SIZE)

        relationships_query = await DeleteBranchAgnosticRelationshipsQuery.init(
            db=self.db, branch_name=branch_name, batch_size=batch_size
        )
        await relationships_query.execute(db=self.db)

        attributes_query = await DeleteBranchAgnosticAttributesQuery.init(
            db=self.db, branch_name=branch_name, batch_size=batch_size
        )
        await attributes_query.execute(db=self.db)

        edges_removed = relationships_query.stats.get_counter(
            "relationships_deleted"
        ) + attributes_query.stats.get_counter("relationships_deleted")
        if edges_removed:
            self.log.info(
                f"Deleted agnostic peers of nodes only on branch '{branch_name}', {edges_removed} edge(s) removed"
            )
        return edges_removed

    async def _delete_edges(self, branch_name: str) -> int:
        edges_removed = 0
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
                edges_removed += deleted_total
                self.log.info(f"Deleted {deleted_total} {edge_type.value} edge(s) on branch '{branch_name}'")

        return edges_removed
