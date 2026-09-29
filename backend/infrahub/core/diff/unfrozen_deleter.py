from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .diff_locker import DiffLocker
    from .model.path import EnrichedDiffRootMetadata
    from .repository.repository import DiffRepository


@dataclass(frozen=True)
class UnfrozenDiffBatch:
    """The unfrozen diffs stored for one branch against its base branch."""

    base_branch_name: str
    diff_branch_name: str
    diffs: tuple[tuple[str, ...], ...]
    """Root uuids of each diff: a root together with the root it is paired with, or a root left alone."""

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

    @property
    def num_diffs(self) -> int:
        return sum(len(batch.diffs) for batch in self.batches)

    @classmethod
    def from_roots(cls, roots: Iterable[EnrichedDiffRootMetadata], branch_name: str | None) -> Self:
        """Group the unfrozen diffs among the roots by the branch whose diff update lock covers them.

        Args:
            branch_name: Only plan the diffs of this branch; every branch when None.

        """
        roots_by_uuid = {root.uuid: root for root in roots}
        handled_uuids: set[str] = set()
        diffs_by_branches: dict[tuple[str, str], list[tuple[str, ...]]] = defaultdict(list)
        kept_root_uuids: list[str] = []
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
            if any(member.is_frozen for member in members):
                # Deleting a root also deletes whatever its partner edge points to.
                kept_root_uuids.extend(member.uuid for member in members if not member.is_frozen)
                continue
            diffs_by_branches[root.base_branch_name, root.diff_branch_name].append(
                tuple(member.uuid for member in members)
            )

        batches = tuple(
            UnfrozenDiffBatch(base_branch_name=base_branch_name, diff_branch_name=diff_branch_name, diffs=tuple(diffs))
            for (base_branch_name, diff_branch_name), diffs in sorted(diffs_by_branches.items())
        )
        return cls(batches=batches, kept_root_uuids=tuple(kept_root_uuids))


class UnfrozenDiffDeleter:
    """Delete the stored diffs that are not frozen, one branch at a time."""

    def __init__(self, diff_repository: DiffRepository, diff_locker: DiffLocker) -> None:
        self.diff_repository = diff_repository
        self.diff_locker = diff_locker

    async def plan(self, branch_name: str | None) -> UnfrozenDiffDeletionPlan:
        """List the unfrozen diffs of branch_name, or of every branch when it is None."""
        roots = await self.diff_repository.get_roots_metadata(exclude_merged=False)
        return UnfrozenDiffDeletionPlan.from_roots(roots=roots, branch_name=branch_name)

    async def delete(self, batch: UnfrozenDiffBatch) -> None:
        """Delete the diffs of the batch once no diff update of its branch is in progress.

        A root frozen since the batch was planned is kept.
        """
        async with (
            self.diff_locker.acquire_lock(
                target_branch_name=batch.base_branch_name,
                source_branch_name=batch.diff_branch_name,
                is_incremental=True,
            ),
            self.diff_locker.acquire_lock(
                target_branch_name=batch.base_branch_name,
                source_branch_name=batch.diff_branch_name,
                is_incremental=False,
            ),
        ):
            await self.diff_repository.delete_diff_roots(diff_root_uuids=batch.root_uuids)
