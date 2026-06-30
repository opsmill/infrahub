from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.diff.model.path import BranchTrackingId
from infrahub.exceptions import (
    MergeConflictsUnresolvedError,
    MergeConstraintsViolatedError,
    MergeFailedError,
    ValidationError,
)
from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.diff.coordinator import DiffCoordinator
    from infrahub.core.diff.diff_locker import DiffLocker
    from infrahub.core.diff.merger.merger import DiffMerger
    from infrahub.core.diff.repository.repository import DiffRepository
    from infrahub.core.merge.constraints import MergeConstraintValidator
    from infrahub.core.merge.schema_analyzer import MergeSchemaAnalyzer
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
        schema_analyzer: MergeSchemaAnalyzer,
        constraint_validator: MergeConstraintValidator,
        logger: InfrahubLogger | None = None,
    ) -> None:
        self.db = db
        self.source_branch = source_branch
        self.destination_branch = destination_branch
        self.diff_coordinator = diff_coordinator
        self.diff_merger = diff_merger
        self.diff_repository = diff_repository
        self.diff_locker = diff_locker
        self.schema_analyzer = schema_analyzer
        self.constraint_validator = constraint_validator
        self.log = logger or get_logger()

    async def merge(self, at: Timestamp) -> None:
        """Merge the current branch into the default branch.

        Raises:
            ValidationError: When the source branch is the default branch.
            MergeConflictsUnresolvedError: When the branch has conflicts that are not resolved.
            MergeConstraintsViolatedError: When the merged state would violate a constraint.
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

            # Pre-merge gates run before the graph is mutated, under the diff lock and against the
            # freshly-recomputed diff, so a violation introduced after a proposed change's pipeline ran
            # (e.g. another branch merging the same unique value) is still caught.
            await self._validate_no_unresolved_conflicts()
            await self._validate_constraints()

            try:
                await self.diff_merger.merge_graph(at=at)
            except Exception as exc:
                # Rollback is handled outside of this class b/c there is more than just the graph changes to revert
                self.log.exception("Graph merge failed")
                raise MergeFailedError(branch_name=self.source_branch.name) from exc

    async def _validate_no_unresolved_conflicts(self) -> None:
        """Raise if the branch still has conflicts with the destination that have not been resolved.

        Raises:
            MergeConflictsUnresolvedError: When one or more conflicts lack a resolution.

        """
        errors: list[str] = []
        async for conflict_path, conflict in self.diff_repository.get_all_conflicts_for_diff(
            diff_branch_name=self.source_branch.name,
            tracking_id=BranchTrackingId(name=self.source_branch.name),
        ):
            if conflict.selected_branch is None or conflict.resolvable is False:
                errors.append(conflict_path)
        if errors:
            raise MergeConflictsUnresolvedError(conflict_paths=errors, branch_name=self.source_branch.name)

    async def _validate_constraints(self) -> None:
        """Raise if merging the branch would violate a schema/data constraint on the destination.

        Raises:
            MergeConstraintsViolatedError: When the merged state would violate a constraint.

        """
        candidate_schema = self.schema_analyzer.get_candidate_schema()
        # Gate on the freshly-recomputed diff (same check the migration calculation uses) rather than
        # the branch's cached schema-hash flag, so a schema change is never missed at merge time.
        schema_diff_constraints = (
            await self.schema_analyzer.calculate_validations(target_schema=candidate_schema)
            if await self.schema_analyzer.has_schema_changes()
            else []
        )
        result = await self.constraint_validator.validate(
            candidate_schema=candidate_schema, schema_diff_constraints=schema_diff_constraints
        )
        if result.violations:
            raise MergeConstraintsViolatedError(violations=result.violations, schema_conflicts=result.schema_conflicts)

    async def rollback(self, at: Timestamp) -> None:
        await self.diff_merger.rollback(at=at)
