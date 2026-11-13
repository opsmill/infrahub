from dataclasses import dataclass
from uuid import uuid4

import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import RepositoryInternalStatus, RepositorySyncStatus, ValidatorConclusion
from infrahub.core.merge.repository_import_guard import RepositoryImportGuard
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import MergeRepositoryImportError
from infrahub.git.sync_status import (
    BranchImportVerdict,
    RepositoryBranchSyncStatus,
    RepositoryBranchSyncStatusReader,
    classify_branch_import,
    is_written_on_branch,
)
from infrahub.git.tasks import evaluate_import_status


class StaticStatusReader(RepositoryBranchSyncStatusReader):
    """Answers every read with the statuses it was built with."""

    def __init__(self, statuses: list[RepositoryBranchSyncStatus]) -> None:
        self.statuses = statuses

    async def list_statuses_on_branch(self, branch: Branch) -> list[RepositoryBranchSyncStatus]:
        return self.statuses


def active(repository_name: str, sync_status: RepositorySyncStatus | None) -> RepositoryBranchSyncStatus:
    return RepositoryBranchSyncStatus(
        repository_name=repository_name, internal_status=RepositoryInternalStatus.ACTIVE, sync_status=sync_status
    )


def feature_branch() -> Branch:
    return Branch(name="feature", uuid=uuid4())


@dataclass(frozen=True, kw_only=True)
class VerdictCase:
    name: str
    sync_status: RepositorySyncStatus
    verdict: BranchImportVerdict
    blocks_merge: bool


VERDICT_CASES = [
    VerdictCase(
        name="in_sync", sync_status=RepositorySyncStatus.IN_SYNC, verdict=BranchImportVerdict.USABLE, blocks_merge=False
    ),
    VerdictCase(
        name="error_import",
        sync_status=RepositorySyncStatus.ERROR_IMPORT,
        verdict=BranchImportVerdict.FAILED,
        blocks_merge=True,
    ),
    VerdictCase(
        name="error_ref_missing",
        sync_status=RepositorySyncStatus.ERROR_REF_MISSING,
        verdict=BranchImportVerdict.REF_MISSING,
        blocks_merge=True,
    ),
    VerdictCase(
        name="syncing",
        sync_status=RepositorySyncStatus.SYNCING,
        verdict=BranchImportVerdict.INCOMPLETE,
        blocks_merge=True,
    ),
    VerdictCase(
        name="unknown",
        sync_status=RepositorySyncStatus.UNKNOWN,
        verdict=BranchImportVerdict.INCOMPLETE,
        blocks_merge=True,
    ),
]


def test_every_sync_status_has_a_verdict_case() -> None:
    assert {case.sync_status for case in VERDICT_CASES} == set(RepositorySyncStatus)


@pytest.mark.parametrize("case", VERDICT_CASES, ids=[case.name for case in VERDICT_CASES])
def test_each_sync_status_classifies_to_its_verdict(case: VerdictCase) -> None:
    verdict = classify_branch_import(sync_status=case.sync_status, internal_status=RepositoryInternalStatus.ACTIVE)

    assert (verdict, verdict.blocks_merge) == (case.verdict, case.blocks_merge)


@pytest.mark.parametrize("case", VERDICT_CASES, ids=[case.name for case in VERDICT_CASES])
async def test_the_merge_guard_refuses_exactly_the_statuses_whose_verdict_blocks(case: VerdictCase) -> None:
    guard = RepositoryImportGuard(status_reader=StaticStatusReader([active("repo", case.sync_status)]))

    try:
        await guard.verify(branch=feature_branch())
    except MergeRepositoryImportError:
        refused = True
    else:
        refused = False

    assert refused is case.blocks_merge


@pytest.mark.parametrize("case", VERDICT_CASES, ids=[case.name for case in VERDICT_CASES])
def test_the_proposed_change_check_fails_exactly_the_statuses_whose_verdict_blocks(case: VerdictCase) -> None:
    outcome = evaluate_import_status(
        sync_status=case.sync_status,
        internal_status=RepositoryInternalStatus.ACTIVE,
        repository_name="repo",
        branch_name="feature",
        tracked_ref=None,
    )

    assert (outcome.conclusion is ValidatorConclusion.FAILURE) is case.blocks_merge


async def test_the_merge_guard_refuses_a_branch_marked_ref_missing_with_the_ref_missing_message() -> None:
    guard = RepositoryImportGuard(
        status_reader=StaticStatusReader(
            [
                RepositoryBranchSyncStatus(
                    repository_name="readonly-repo",
                    internal_status=RepositoryInternalStatus.ACTIVE,
                    sync_status=RepositorySyncStatus.ERROR_REF_MISSING,
                    tracked_ref="v1.0",
                )
            ]
        )
    )

    with pytest.raises(
        MergeRepositoryImportError,
        match=(
            r"^Cannot merge\. The tracked ref 'v1\.0' of repository 'readonly-repo' was missing from the remote when "
            r"last checked: restore the ref or edit the ref of the repository, then reimport the current commit\.$"
        ),
    ):
        await guard.verify(branch=feature_branch())


async def test_the_merge_guard_accepts_a_branch_with_no_status_written_on_it() -> None:
    guard = RepositoryImportGuard(status_reader=StaticStatusReader([active("readonly-repo", None)]))

    await guard.verify(branch=feature_branch())


BRANCHED_FROM = "2026-10-01T12:00:00.000000Z"


@dataclass(frozen=True, kw_only=True)
class WrittenOnBranchCase:
    name: str
    updated_at: str | None
    written: bool


WRITTEN_ON_BRANCH_CASES = [
    WrittenOnBranchCase(
        name="updated_before_the_branch_is_inherited", updated_at="2026-10-01T11:59:59.000000Z", written=False
    ),
    WrittenOnBranchCase(name="updated_at_the_rebase_time_is_written", updated_at=BRANCHED_FROM, written=True),
    WrittenOnBranchCase(
        name="updated_after_the_branch_is_written", updated_at="2026-10-01T12:00:01.000000Z", written=True
    ),
    WrittenOnBranchCase(name="unknown_update_time_counts_as_written", updated_at=None, written=True),
]


@pytest.mark.parametrize("case", WRITTEN_ON_BRANCH_CASES, ids=[case.name for case in WRITTEN_ON_BRANCH_CASES])
def test_a_status_counts_as_written_on_a_branch_from_its_update_time(case: WrittenOnBranchCase) -> None:
    branch = Branch(name="feature", uuid=uuid4(), branched_from=BRANCHED_FROM)
    updated_at = Timestamp(case.updated_at) if case.updated_at is not None else None

    assert is_written_on_branch(updated_at=updated_at, branch=branch) is case.written
