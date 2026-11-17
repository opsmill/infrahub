from __future__ import annotations

from collections import defaultdict
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.branch.filters import BranchListFilters

from .model.path import BranchTrackingId, NameTrackingId

if TYPE_CHECKING:
    from infrahub.core.merge.merge_locker import MergeLocker
    from infrahub.database import InfrahubDatabase

    from .diff_locker import DiffLocker
    from .repository.repository import DiffRepository


@dataclass(frozen=True)
class UnfrozenDiffBatch:
    """The unfrozen diffs stored for one branch against its base branch."""

    base_branch_name: str
    diff_branch_name: str
    diffs: tuple[tuple[str, ...], ...]
    """Root uuids of each diff: a root together with the root it is paired with, or a root left alone."""

    has_branch_diffs: bool
    """Whether one of the diffs tracks its branch, which a merge of that branch reads."""

    def __post_init__(self) -> None:
        # The delete query falls back to every unfrozen diff when it is given no uuid.
        if not self.diffs or not all(self.diffs):
            raise ValueError("An unfrozen diff batch needs at least one diff root to delete")

    @property
    def root_uuids(self) -> list[str]:
        return [root_uuid for diff in self.diffs for root_uuid in diff]


@dataclass(frozen=True)
class UnfrozenDiffDeletionPlan:
    batches: tuple[UnfrozenDiffBatch, ...]
    kept_root_uuids: tuple[str, ...]
    """Unfrozen roots left in place because the root they are paired with is frozen."""

    kept_merged_branch_root_uuids: tuple[str, ...]
    """Unfrozen roots of the diffs tracking a merged branch, left in place because they cannot be calculated again."""

    @property
    def num_diffs(self) -> int:
        return sum(len(batch.diffs) for batch in self.batches)


class UnfrozenDiffDeletionPlanner:
    """Find the stored diffs that are not frozen, grouped by the branch whose diff update lock covers them."""

    def __init__(self, db: InfrahubDatabase, diff_repository: DiffRepository) -> None:
        self.db = db
        self.diff_repository = diff_repository

    async def plan(self, branch_name: str | None, include_branch_diffs: bool) -> UnfrozenDiffDeletionPlan:
        """List the unfrozen named diffs, and the unfrozen branch diffs too when include_branch_diffs is set.

        Args:
            branch_name: Only plan the diffs of this branch; every branch when None.

        """
        roots = await self.diff_repository.get_roots_metadata(exclude_merged=False)
        merged_branch_names = await self._get_merged_branch_names() if include_branch_diffs else set()
        roots_by_uuid = {root.uuid: root for root in roots}
        handled_uuids: set[str] = set()
        diffs_by_branches: dict[tuple[str, str], list[tuple[str, ...]]] = defaultdict(list)
        branches_with_branch_diffs: set[tuple[str, str]] = set()
        kept_root_uuids: list[str] = []
        kept_merged_branch_root_uuids: list[str] = []
        # Branch roots go first, so that a base root is grouped under the branch it is paired with.
        for root in sorted(roots_by_uuid.values(), key=lambda r: r.base_branch_name == r.diff_branch_name):
            if root.uuid in handled_uuids:
                continue
            members = [root]
            partner = roots_by_uuid.get(root.partner_uuid) if root.partner_uuid else None
            if partner is not None and partner.uuid not in handled_uuids:
                members.append(partner)
            handled_uuids.update(member.uuid for member in members)

            if branch_name is not None and root.diff_branch_name != branch_name:
                continue
            tracks_branch = any(isinstance(member.tracking_id, BranchTrackingId) for member in members)
            if not include_branch_diffs and not any(
                isinstance(member.tracking_id, NameTrackingId) for member in members
            ):
                continue
            if any(member.is_frozen for member in members):
                # Deleting a root also deletes whatever its partner edge points to.
                kept_root_uuids.extend(member.uuid for member in members if not member.is_frozen)
                continue
            if tracks_branch and root.diff_branch_name in merged_branch_names:
                kept_merged_branch_root_uuids.extend(member.uuid for member in members)
                continue
            branches = (root.base_branch_name, root.diff_branch_name)
            diffs_by_branches[branches].append(tuple(member.uuid for member in members))
            if tracks_branch:
                branches_with_branch_diffs.add(branches)

        batches = tuple(
            UnfrozenDiffBatch(
                base_branch_name=base_branch_name,
                diff_branch_name=diff_branch_name,
                diffs=tuple(diffs),
                has_branch_diffs=(base_branch_name, diff_branch_name) in branches_with_branch_diffs,
            )
            for (base_branch_name, diff_branch_name), diffs in sorted(diffs_by_branches.items())
        )
        return UnfrozenDiffDeletionPlan(
            batches=batches,
            kept_root_uuids=tuple(kept_root_uuids),
            kept_merged_branch_root_uuids=tuple(kept_merged_branch_root_uuids),
        )

    async def _get_merged_branch_names(self) -> set[str]:
        merged_filter = BranchListFilters(status=BranchStatus.MERGED)
        # The branch list stops at a page size, so the page is sized from the count.
        num_merged = await Branch.get_list_count(db=self.db, branch_filters=merged_filter)
        if not num_merged:
            return set()
        branches = await Branch.get_list(db=self.db, branch_filters=merged_filter, limit=num_merged)
        return {branch.name for branch in branches}


class UnfrozenDiffDeleter:
    """Delete the diffs of an unfrozen diff deletion plan, one branch at a time."""

    def __init__(self, diff_repository: DiffRepository, diff_locker: DiffLocker, merge_locker: MergeLocker) -> None:
        self.diff_repository = diff_repository
        self.diff_locker = diff_locker
        self.merge_locker = merge_locker

    async def delete(self, plan: UnfrozenDiffDeletionPlan) -> None:
        """Delete the planned diffs of each branch once no diff update of that branch is in progress.

        Branch diffs are also deleted only once no merge is in progress. A root frozen since the plan
        was made is kept.
        """
        for batch in plan.batches:
            async with AsyncExitStack() as locks:
                # A merge reads and freezes its branch diff outside the diff update locks, holding the
                # merge lock it takes before them.
                if batch.has_branch_diffs:
                    await locks.enter_async_context(self.merge_locker.acquire_global_lock())
                await locks.enter_async_context(
                    self.diff_locker.acquire_lock(
                        target_branch_name=batch.base_branch_name,
                        source_branch_name=batch.diff_branch_name,
                        is_incremental=True,
                    )
                )
                await locks.enter_async_context(
                    self.diff_locker.acquire_lock(
                        target_branch_name=batch.base_branch_name,
                        source_branch_name=batch.diff_branch_name,
                        is_incremental=False,
                    )
                )
                await self.diff_repository.delete_diff_roots(diff_root_uuids=batch.root_uuids)
