import re
from dataclasses import dataclass

import pytest
from pydantic import ValidationError

from infrahub.message_bus.messages.refresh_git_fetch import BranchCommitPair, RefreshGitFetch

TRUNK = BranchCommitPair(infrahub_branch_name="main", infrahub_branch_id="main-id", commit="a" * 40)
FEATURE = BranchCommitPair(infrahub_branch_name="feature", infrahub_branch_id="feature-id", commit="b" * 40)


def build_message(branches: tuple[BranchCommitPair, ...] | None, commit: str | None = TRUNK.commit) -> RefreshGitFetch:
    return RefreshGitFetch(
        location="https://git.example.com/repo.git",
        repository_id="repository-id",
        repository_name="repo",
        repository_kind="CoreRepository",
        infrahub_branch_name=TRUNK.infrahub_branch_name,
        infrahub_branch_id=TRUNK.infrahub_branch_id,
        commit=commit,
        branches=branches,
    )


@dataclass
class AcceptedCase:
    name: str
    branches: tuple[BranchCommitPair, ...] | None


ACCEPTED_CASES = [
    AcceptedCase(name="no_branch_list", branches=None),
    AcceptedCase(name="list_of_the_single_branch", branches=(TRUNK,)),
    AcceptedCase(name="later_entries_name_other_branches", branches=(TRUNK, FEATURE)),
]


@pytest.mark.parametrize("case", ACCEPTED_CASES, ids=[case.name for case in ACCEPTED_CASES])
def test_a_branch_list_starting_with_the_single_branch_fields_is_accepted(case: AcceptedCase) -> None:
    assert build_message(branches=case.branches).branches == case.branches


@dataclass
class RejectedCase:
    name: str
    branches: tuple[BranchCommitPair, ...]
    commit: str | None
    error: str


REJECTED_CASES = [
    RejectedCase(
        name="first_entry_is_another_branch",
        branches=(FEATURE, TRUNK),
        commit=TRUNK.commit,
        error=(
            f"The first entry of branches (feature, feature-id, {FEATURE.commit}) differs from the single-branch "
            f"fields (main, main-id, {TRUNK.commit})"
        ),
    ),
    RejectedCase(
        name="first_entry_pins_another_commit",
        branches=(TRUNK,),
        commit=FEATURE.commit,
        error=(
            f"The first entry of branches (main, main-id, {TRUNK.commit}) differs from the single-branch "
            f"fields (main, main-id, {FEATURE.commit})"
        ),
    ),
    RejectedCase(
        name="single_branch_fields_pin_no_commit",
        branches=(TRUNK,),
        commit=None,
        error=(
            f"The first entry of branches (main, main-id, {TRUNK.commit}) differs from the single-branch "
            "fields (main, main-id, None)"
        ),
    ),
    RejectedCase(
        name="empty_list",
        branches=(),
        commit=TRUNK.commit,
        error="branches must hold at least one branch when it is set",
    ),
]


@pytest.mark.parametrize("case", REJECTED_CASES, ids=[case.name for case in REJECTED_CASES])
def test_a_branch_list_not_starting_with_the_single_branch_fields_is_rejected(case: RejectedCase) -> None:
    """A worker that reads only the single-branch fields would converge a branch the list does not start with."""
    with pytest.raises(ValidationError, match=rf"Value error, {re.escape(case.error)} \["):
        build_message(branches=case.branches, commit=case.commit)
