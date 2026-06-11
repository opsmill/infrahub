from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.branch.status_checker import MERGE_IN_PROGRESS_MESSAGE, BranchStatusChecker
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.merge.write_blocker import MergeProtectionState, MergeWriteBlocker
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import BranchAlreadyMergedError, BranchNeedsRebaseError
from tests.adapters.cache import MemoryCache, UnreachableCache

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from infrahub.database import InfrahubDatabase


def _checker(db: InfrahubDatabase, blocker: MergeWriteBlocker | None = None) -> BranchStatusChecker:
    return BranchStatusChecker(db=db, merge_write_blocker=blocker or MergeWriteBlocker(cache=MemoryCache()))


class TestBranchStatusChecker:
    """Component tests for the write gate (it requires a real db, loaded once per class).

    Cache-key-driven gate decisions use in-memory branches; the cache-unreachable fallback is
    exercised against persisted branch statuses.
    """

    # --- basic status checks (no protection key) ---

    async def test_open_branch_passes(self, db: InfrahubDatabase) -> None:
        await _checker(db).check(branch=Branch(name="open-branch", status=BranchStatus.OPEN))

    async def test_merged_branch_raises(self, db: InfrahubDatabase) -> None:
        branch = Branch(name="merged-branch", status=BranchStatus.MERGED)
        with pytest.raises(BranchAlreadyMergedError, match=r"merged-branch.*has been merged and is read-only"):
            await _checker(db).check(branch=branch)

    async def test_check_merge_status_ignores_merging(self, db: InfrahubDatabase) -> None:
        # MERGING is gated by the shared merge-protection cache key, not by check_merge_status.
        _checker(db).check_merge_status(branch=Branch(name="merging-branch", status=BranchStatus.MERGING))

    async def test_need_rebase_raises(self, db: InfrahubDatabase) -> None:
        branch = Branch(name="rebase-branch", status=BranchStatus.NEED_REBASE)
        with pytest.raises(BranchNeedsRebaseError, match=r"rebase-branch.*must be rebased"):
            await _checker(db).check(branch=branch)

    async def test_need_upgrade_rebase_passes(self, db: InfrahubDatabase) -> None:
        await _checker(db).check(branch=Branch(name="upgrade-branch", status=BranchStatus.NEED_UPGRADE_REBASE))

    async def test_deleting_passes(self, db: InfrahubDatabase) -> None:
        await _checker(db).check(branch=Branch(name="deleting-branch", status=BranchStatus.DELETING))

    # --- cache-key-driven gates ---

    async def test_blocks_source_branch_while_protected(self, db: InfrahubDatabase) -> None:
        blocker = MergeWriteBlocker(cache=MemoryCache())
        await blocker.set(branch="feature-branch", state=MergeProtectionState.MERGING)
        branch = Branch(name="feature-branch", status=BranchStatus.MERGING)
        with pytest.raises(BranchAlreadyMergedError, match=r"feature-branch.*is being merged and is read-only"):
            await _checker(db, blocker).check(branch=branch)

    async def test_blocks_default_branch_while_protected(self, db: InfrahubDatabase) -> None:
        blocker = MergeWriteBlocker(cache=MemoryCache())
        await blocker.set(branch="feature-branch", state=MergeProtectionState.MERGING)
        branch = Branch(name="main", status=BranchStatus.OPEN, is_default=True)
        with pytest.raises(BranchAlreadyMergedError, match=MERGE_IN_PROGRESS_MESSAGE):
            await _checker(db, blocker).check(branch=branch)

    async def test_unrelated_branch_writable_while_protected(self, db: InfrahubDatabase) -> None:
        blocker = MergeWriteBlocker(cache=MemoryCache())
        await blocker.set(branch="feature-branch", state=MergeProtectionState.MERGING)
        await _checker(db, blocker).check(branch=Branch(name="other-branch", status=BranchStatus.OPEN))

    async def test_block_lifts_when_key_cleared(self, db: InfrahubDatabase) -> None:
        blocker = MergeWriteBlocker(cache=MemoryCache())
        await blocker.set(branch="feature-branch", state=MergeProtectionState.MERGING)
        checker = _checker(db, blocker)
        default_branch = Branch(name="main", status=BranchStatus.OPEN, is_default=True)

        with pytest.raises(BranchAlreadyMergedError, match=MERGE_IN_PROGRESS_MESSAGE):
            await checker.check(branch=default_branch)

        await blocker.delete()
        await checker.check(branch=default_branch)

    # --- cache-unreachable fallback to the durable DB status ---

    async def test_cache_unreachable_no_merge_allows_default(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch
    ) -> None:
        """A cache outage with no merge in progress must not freeze the default branch."""
        checker = _checker(db, MergeWriteBlocker(cache=UnreachableCache()))
        await checker.check(branch=default_branch_scope_class)

    @pytest.fixture
    async def persisted_merging_branch(self, db: InfrahubDatabase) -> AsyncGenerator[Branch, None]:
        """A branch persisted in MERGING; reset to OPEN on teardown so the class-shared db stays clean."""
        branch = Branch(
            name="status-checker-db-merging", status=BranchStatus.MERGING, branched_from=Timestamp().to_string()
        )
        await branch.save(db=db)
        yield branch
        branch.status = BranchStatus.OPEN
        await branch.save(db=db)

    async def test_cache_unreachable_with_merge_blocks_via_db(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, persisted_merging_branch: Branch
    ) -> None:
        open_branch = Branch(
            name="status-checker-db-open", status=BranchStatus.OPEN, branched_from=Timestamp().to_string()
        )
        await open_branch.save(db=db)
        checker = _checker(db, MergeWriteBlocker(cache=UnreachableCache()))

        with pytest.raises(BranchAlreadyMergedError, match=MERGE_IN_PROGRESS_MESSAGE):
            await checker.check(branch=default_branch_scope_class)

        with pytest.raises(
            BranchAlreadyMergedError, match=r"status-checker-db-merging.*is being merged and is read-only"
        ):
            await checker.check(branch=persisted_merging_branch)

        await checker.check(branch=open_branch)
