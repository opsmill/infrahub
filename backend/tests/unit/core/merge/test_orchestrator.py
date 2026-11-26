from __future__ import annotations

import pytest

from infrahub.core.merge.orchestrator import refuse_merge_under_protection
from infrahub.core.merge.write_blocker import MergeProtection, MergeProtectionState
from infrahub.exceptions import MergeRecoveryRequiredError, MergeRefusedError


def test_a_merge_goes_on_without_a_protection() -> None:
    refuse_merge_under_protection(protection=None, source_branch="branch-c")


def test_a_merge_goes_on_under_its_own_protection() -> None:
    """The merge flow can run again for the branch whose merge set the protection."""
    refuse_merge_under_protection(
        protection=MergeProtection(branch="branch-c", state=MergeProtectionState.MERGING), source_branch="branch-c"
    )


def test_the_merge_of_another_branch_in_progress_refuses_the_merge() -> None:
    with pytest.raises(MergeRefusedError, match=r"^Cannot merge a branch while a merge is in progress\.$"):
        refuse_merge_under_protection(
            protection=MergeProtection(branch="branch-a", state=MergeProtectionState.MERGING),
            source_branch="branch-c",
        )


def test_a_failed_merge_of_another_branch_asks_for_recovery() -> None:
    """A failed merge needs an administrator, so it is not reported as a merge in progress."""
    with pytest.raises(
        MergeRecoveryRequiredError,
        match=(
            r"^Cannot merge, because the merge of branch branch-a failed and left the default branch protected\. "
            r"An administrator must run `infrahub recover merge` before another merge\.$"
        ),
    ) as refusal:
        refuse_merge_under_protection(
            protection=MergeProtection(branch="branch-a", state=MergeProtectionState.MERGE_FAILED),
            source_branch="branch-c",
        )

    assert (refusal.value.identifier, refusal.value.merging_branch) == ("branch-c", "branch-a")
