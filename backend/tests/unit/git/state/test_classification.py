from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.core.constants import RepositoryCommitState, RepositoryGitCondition
from infrahub.git.state.classification import classify, classify_commit
from infrahub.git.state.models import GitStateFacts

HEAD = "3333333333333333333333333333333333333333"
MIDDLE = "2222222222222222222222222222222222222222"
IMPORTED = "1111111111111111111111111111111111111111"
ROOT = "0000000000000000000000000000000000000000"

BEHIND_FACTS = GitStateFacts(
    head=HEAD, imported=IMPORTED, imported_resolvable=True, imported_is_ancestor_of_head=True, ref_is_configured=False
)
IN_SYNC_FACTS = GitStateFacts(
    head=IMPORTED,
    imported=IMPORTED,
    imported_resolvable=True,
    imported_is_ancestor_of_head=True,
    ref_is_configured=False,
)
REWRITTEN_FACTS = GitStateFacts(
    head=HEAD, imported=IMPORTED, imported_resolvable=True, imported_is_ancestor_of_head=False, ref_is_configured=False
)
ORPHANED_FACTS = GitStateFacts(head=HEAD, imported=IMPORTED, imported_resolvable=False, ref_is_configured=False)
NOT_TRACKED_FACTS = GitStateFacts(head=HEAD, imported=None, ref_is_configured=False)
REF_MISSING_FACTS = GitStateFacts(head=None, imported=IMPORTED, imported_resolvable=True, ref_is_configured=True)


@dataclass(frozen=True)
class ConditionCase:
    name: str
    facts: GitStateFacts
    expected: RepositoryGitCondition


CONDITION_CASES = [
    ConditionCase(
        name="head_equal_to_imported_is_in_sync", facts=IN_SYNC_FACTS, expected=RepositoryGitCondition.IN_SYNC
    ),
    ConditionCase(
        name="imported_ancestor_of_head_is_behind", facts=BEHIND_FACTS, expected=RepositoryGitCondition.BEHIND
    ),
    ConditionCase(
        name="imported_not_ancestor_of_head_is_rewritten",
        facts=REWRITTEN_FACTS,
        expected=RepositoryGitCondition.REWRITTEN,
    ),
    ConditionCase(
        name="unresolvable_imported_is_orphaned_without_any_ancestry_answer",
        facts=ORPHANED_FACTS,
        expected=RepositoryGitCondition.ORPHANED,
    ),
    ConditionCase(
        name="unresolvable_imported_is_orphaned_even_with_no_head",
        facts=GitStateFacts(head=None, imported=IMPORTED, imported_resolvable=False, ref_is_configured=False),
        expected=RepositoryGitCondition.ORPHANED,
    ),
    ConditionCase(
        name="no_head_for_a_mapped_branch_is_no_remote",
        facts=GitStateFacts(head=None, imported=IMPORTED, imported_resolvable=True, ref_is_configured=False),
        expected=RepositoryGitCondition.NO_REMOTE,
    ),
    ConditionCase(
        name="nothing_imported_is_not_tracked",
        facts=NOT_TRACKED_FACTS,
        expected=RepositoryGitCondition.NOT_TRACKED,
    ),
    ConditionCase(
        name="nothing_imported_and_no_head_is_not_tracked",
        facts=GitStateFacts(head=None, imported=None, ref_is_configured=False),
        expected=RepositoryGitCondition.NOT_TRACKED,
    ),
    ConditionCase(
        name="configured_ref_with_no_head_is_ref_missing",
        facts=REF_MISSING_FACTS,
        expected=RepositoryGitCondition.REF_MISSING,
    ),
    ConditionCase(
        name="configured_ref_with_no_head_is_ref_missing_even_with_nothing_imported",
        facts=GitStateFacts(head=None, imported=None, ref_is_configured=True),
        expected=RepositoryGitCondition.REF_MISSING,
    ),
    ConditionCase(
        name="unresolvable_imported_is_orphaned_before_a_missing_configured_ref",
        facts=GitStateFacts(head=None, imported=IMPORTED, imported_resolvable=False, ref_is_configured=True),
        expected=RepositoryGitCondition.ORPHANED,
    ),
    ConditionCase(
        name="configured_ref_with_a_head_classifies_by_ancestry",
        facts=GitStateFacts(
            head=HEAD,
            imported=IMPORTED,
            imported_resolvable=True,
            imported_is_ancestor_of_head=True,
            ref_is_configured=True,
        ),
        expected=RepositoryGitCondition.BEHIND,
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in CONDITION_CASES])
def test_classify(case: ConditionCase) -> None:
    assert classify(facts=case.facts) is case.expected


@dataclass(frozen=True)
class CommitCase:
    name: str
    commit_hash: str
    is_pending: bool
    facts: GitStateFacts
    expected: RepositoryCommitState


COMMIT_CASES = [
    CommitCase(
        name="behind_head", commit_hash=HEAD, is_pending=True, facts=BEHIND_FACTS, expected=RepositoryCommitState.HEAD
    ),
    CommitCase(
        name="behind_commit_between_imported_and_head_is_pending",
        commit_hash=MIDDLE,
        is_pending=True,
        facts=BEHIND_FACTS,
        expected=RepositoryCommitState.PENDING,
    ),
    CommitCase(
        name="behind_imported",
        commit_hash=IMPORTED,
        is_pending=False,
        facts=BEHIND_FACTS,
        expected=RepositoryCommitState.IMPORTED,
    ),
    CommitCase(
        name="behind_ancestor_of_imported_is_history",
        commit_hash=ROOT,
        is_pending=False,
        facts=BEHIND_FACTS,
        expected=RepositoryCommitState.HISTORY,
    ),
    CommitCase(
        name="in_sync_imported_wins_over_head",
        commit_hash=IMPORTED,
        is_pending=False,
        facts=IN_SYNC_FACTS,
        expected=RepositoryCommitState.IMPORTED,
    ),
    CommitCase(
        name="in_sync_older_commit_is_history",
        commit_hash=ROOT,
        is_pending=False,
        facts=IN_SYNC_FACTS,
        expected=RepositoryCommitState.HISTORY,
    ),
    CommitCase(
        name="rewritten_head",
        commit_hash=HEAD,
        is_pending=False,
        facts=REWRITTEN_FACTS,
        expected=RepositoryCommitState.HEAD,
    ),
    CommitCase(
        name="rewritten_shared_ancestor_of_imported_is_unrelated",
        commit_hash=ROOT,
        is_pending=False,
        facts=REWRITTEN_FACTS,
        expected=RepositoryCommitState.UNRELATED,
    ),
    CommitCase(
        name="orphaned_head",
        commit_hash=HEAD,
        is_pending=False,
        facts=ORPHANED_FACTS,
        expected=RepositoryCommitState.HEAD,
    ),
    CommitCase(
        name="orphaned_other_commit_is_unrelated",
        commit_hash=ROOT,
        is_pending=False,
        facts=ORPHANED_FACTS,
        expected=RepositoryCommitState.UNRELATED,
    ),
    CommitCase(
        name="not_tracked_head",
        commit_hash=HEAD,
        is_pending=False,
        facts=NOT_TRACKED_FACTS,
        expected=RepositoryCommitState.HEAD,
    ),
    CommitCase(
        name="not_tracked_other_commit_is_unrelated",
        commit_hash=ROOT,
        is_pending=False,
        facts=NOT_TRACKED_FACTS,
        expected=RepositoryCommitState.UNRELATED,
    ),
    CommitCase(
        name="ref_missing_imported",
        commit_hash=IMPORTED,
        is_pending=False,
        facts=REF_MISSING_FACTS,
        expected=RepositoryCommitState.IMPORTED,
    ),
    CommitCase(
        name="ref_missing_ancestor_of_imported_is_history",
        commit_hash=ROOT,
        is_pending=False,
        facts=REF_MISSING_FACTS,
        expected=RepositoryCommitState.HISTORY,
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in COMMIT_CASES])
def test_classify_commit(case: CommitCase) -> None:
    state = classify_commit(
        commit_hash=case.commit_hash,
        is_pending=case.is_pending,
        facts=case.facts,
        condition=classify(facts=case.facts),
    )

    assert state is case.expected


def test_non_linear_history_is_classified_by_membership_not_position() -> None:
    """A merged side branch lists pending and imported commits interleaved, newest first by date.

    Walking head (a merge) -> [side-branch tip, imported, older side-branch commit, root] must not
    label a commit pending or history from where it sits in the list.
    """
    side_commit = "4444444444444444444444444444444444444444"
    listed = [(HEAD, True), (side_commit, True), (IMPORTED, False), (MIDDLE, True), (ROOT, False)]

    states = [
        classify_commit(
            commit_hash=commit_hash, is_pending=is_pending, facts=BEHIND_FACTS, condition=RepositoryGitCondition.BEHIND
        )
        for commit_hash, is_pending in listed
    ]

    assert states == [
        RepositoryCommitState.HEAD,
        RepositoryCommitState.PENDING,
        RepositoryCommitState.IMPORTED,
        RepositoryCommitState.PENDING,
        RepositoryCommitState.HISTORY,
    ]
