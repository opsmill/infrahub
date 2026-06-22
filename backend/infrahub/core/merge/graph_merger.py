from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.diff.model.path import BranchTrackingId
from infrahub.exceptions import MergeFailedError, ValidationError
from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.diff.coordinator import DiffCoordinator
    from infrahub.core.diff.diff_locker import DiffLocker
    from infrahub.core.diff.merger.merger import DiffMerger
    from infrahub.core.diff.repository.repository import DiffRepository
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase
    from infrahub.log import InfrahubLogger


class GraphMerger:
    """Apply (or roll back) the graph merge of a source branch into its destination."""

    def __init__(
        self,
        db: InfrahubDatabase,
        source_branch: Branch,
        destination_branch: Branch,
        diff_coordinator: DiffCoordinator,
        diff_merger: DiffMerger,
        diff_repository: DiffRepository,
        diff_locker: DiffLocker,
        logger: InfrahubLogger | None = None,
    ) -> None:
        self.db = db
        self.source_branch = source_branch
        self.destination_branch = destination_branch
        self.diff_coordinator = diff_coordinator
        self.diff_merger = diff_merger
        self.diff_repository = diff_repository
        self.diff_locker = diff_locker
        self.log = logger or get_logger()

    async def merge(self, at: Timestamp) -> None:
        """Merge the current branch into the default branch.

        Raises:
            ValidationError: When the source branch is the default branch or when there are
                unresolved conflicts.
            MergeFailedError: When the underlying graph merge raises an exception.

        """
        if self.source_branch.name == self.destination_branch.name:
            raise ValidationError(f"Unable to merge the branch '{self.source_branch.name}' into itself")
        self.log.info("Updating diff for merge")
        await self.diff_coordinator.update_branch_diff(
            base_branch=self.destination_branch, diff_branch=self.source_branch
        )
        self.log.info("Diff updated for merge")

        self.log.info("Acquiring diff lock for merge")
        async with self.diff_locker.acquire_lock(
            target_branch_name=self.destination_branch.name,
            source_branch_name=self.source_branch.name,
            is_incremental=False,
        ):
            self.log.info("Diff lock acquired for merge")
            errors: list[str] = []
            async for conflict_path, conflict in self.diff_repository.get_all_conflicts_for_diff(
                diff_branch_name=self.source_branch.name,
                tracking_id=BranchTrackingId(name=self.source_branch.name),
            ):
                if conflict.selected_branch is None or conflict.resolvable is False:
                    errors.append(conflict_path)

            if errors:
                raise ValidationError(
                    f"Unable to merge the branch '{self.source_branch.name}', conflict resolution missing: {', '.join(errors)}"
                )

            try:
                await self.diff_merger.merge_graph(at=at)
            except Exception as exc:
                # Rollback is handled outside of this class b/c there is more than just the graph changes to revert
                self.log.exception("Graph merge failed")
                raise MergeFailedError(branch_name=self.source_branch.name) from exc

    async def rollback(self, at: Timestamp) -> None:
        await self.diff_merger.rollback(at=at)
