import pytest

from infrahub.branch.status_checker import BranchStatusChecker
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.initialization import create_branch
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import BranchAlreadyMergedError, BranchLockedForMergeError, BranchNeedsRebaseError


class TestBranchStatusChecker:
    """End-to-end tests for the BranchStatusChecker against a real database.

    All test branches are created once per class so individual test methods do not
    pay the cost of recreating fixtures between runs.
    """

    @pytest.fixture(scope="class", autouse=True)
    async def feature_branches(self, db: InfrahubDatabase, default_branch_scope_class: Branch) -> dict[str, Branch]:
        statuses_by_name = {
            "feature-open": BranchStatus.OPEN,
            "feature-merged": BranchStatus.MERGED,
            "feature-merging": BranchStatus.MERGING,
            "feature-rebase": BranchStatus.NEED_REBASE,
            "feature-upgrade": BranchStatus.NEED_UPGRADE_REBASE,
        }
        branches: dict[str, Branch] = {}
        for name, status in statuses_by_name.items():
            branch = await create_branch(branch_name=name, db=db)
            if branch.status != status:
                branch.status = status
                await branch.save(db=db)
            branches[name] = branch
        return branches

    @pytest.fixture(scope="class")
    def checker(self, db: InfrahubDatabase) -> BranchStatusChecker:
        return BranchStatusChecker(db=db)

    async def test_open_branch_passes(self, checker: BranchStatusChecker, feature_branches: dict[str, Branch]) -> None:
        await checker.check(branch=feature_branches["feature-open"])

    async def test_merged_branch_raises(
        self, checker: BranchStatusChecker, feature_branches: dict[str, Branch]
    ) -> None:
        with pytest.raises(
            BranchAlreadyMergedError,
            match=r"feature-merged.*has been merged and is read-only. No modifications are allowed",
        ):
            await checker.check(branch=feature_branches["feature-merged"])

    async def test_merging_branch_raises(
        self, checker: BranchStatusChecker, feature_branches: dict[str, Branch]
    ) -> None:
        with pytest.raises(
            BranchAlreadyMergedError,
            match=r"feature-merging.*is currently being merged and is read-only. No modifications are allowed",
        ):
            await checker.check(branch=feature_branches["feature-merging"])

    async def test_need_rebase_branch_raises(
        self, checker: BranchStatusChecker, feature_branches: dict[str, Branch]
    ) -> None:
        with pytest.raises(BranchNeedsRebaseError, match=r"feature-rebase.*must be rebased"):
            await checker.check(branch=feature_branches["feature-rebase"])

    async def test_need_upgrade_rebase_branch_passes(
        self, checker: BranchStatusChecker, feature_branches: dict[str, Branch]
    ) -> None:
        await checker.check(branch=feature_branches["feature-upgrade"])

    async def test_db_status_overrides_stale_in_memory_status(
        self, checker: BranchStatusChecker, feature_branches: dict[str, Branch]
    ) -> None:
        """A worker's cached Branch may show OPEN while the DB has flipped to MERGING.
        The checker reads the authoritative status from the DB and refuses the mutation."""
        stale_branch = Branch(name="feature-merging", status=BranchStatus.OPEN)
        with pytest.raises(BranchAlreadyMergedError, match=r"feature-merging.*currently being merged"):
            await checker.check(branch=stale_branch)

    async def test_default_branch_locked_when_other_branch_is_merging(
        self,
        checker: BranchStatusChecker,
        feature_branches: dict[str, Branch],
        default_branch_scope_class: Branch,
    ) -> None:
        with pytest.raises(
            BranchLockedForMergeError,
            match=r"Branch 'main' is locked because branch 'feature-merging' is currently being merged",
        ):
            await checker.check(branch=default_branch_scope_class)
