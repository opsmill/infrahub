from __future__ import annotations

from datetime import UTC, datetime

import pytest

from infrahub.core.constants import RepositoryCommitState, RepositoryGitCondition, RepositoryGitUnavailableReason
from infrahub.git.state.models import BranchDriftResult, CommitEntry, CommitLogResult, GitStateFacts

HEAD = "3333333333333333333333333333333333333333"
IMPORTED = "1111111111111111111111111111111111111111"


def test_unavailable_condition_requires_a_reason() -> None:
    with pytest.raises(ValueError, match=r"^A result with condition UNAVAILABLE must carry an unavailable_reason$"):
        CommitLogResult(condition=RepositoryGitCondition.UNAVAILABLE)


def test_a_reason_requires_the_unavailable_condition() -> None:
    with pytest.raises(
        ValueError,
        match=r"^A result carrying an unavailable_reason must have condition UNAVAILABLE, not BEHIND$",
    ):
        CommitLogResult(
            condition=RepositoryGitCondition.BEHIND,
            unavailable_reason=RepositoryGitUnavailableReason.TIMEOUT,
        )


def test_the_two_agreeing_shapes_are_accepted() -> None:
    unavailable = CommitLogResult(
        condition=RepositoryGitCondition.UNAVAILABLE,
        unavailable_reason=RepositoryGitUnavailableReason.NOT_CLONED,
    )
    answered = CommitLogResult(condition=RepositoryGitCondition.BEHIND, pending_count=3)

    assert unavailable.unavailable_reason is RepositoryGitUnavailableReason.NOT_CLONED
    assert answered.unavailable_reason is None


def test_a_warm_up_belongs_to_the_not_cloned_reason() -> None:
    with pytest.raises(ValueError, match=r"^A warm-up is only started for NOT_CLONED, not TIMEOUT$"):
        CommitLogResult(
            condition=RepositoryGitCondition.UNAVAILABLE,
            unavailable_reason=RepositoryGitUnavailableReason.TIMEOUT,
            warm_up_task_id="18d39e83-1ef7-d650-5424-000000000000",
        )


def test_drift_rows_survive_an_unavailable_column() -> None:
    """FR-022: the rows are graph-resolved, so they stand whatever the git-derived column says."""
    result = BranchDriftResult(
        unavailable_reason=RepositoryGitUnavailableReason.TIMEOUT,
        error_message="No worker answered within the configured time.",
    )

    assert result.unavailable_reason is RepositoryGitUnavailableReason.TIMEOUT
    assert result.branches == ()


def test_an_error_message_belongs_to_an_unavailable_result() -> None:
    with pytest.raises(ValueError, match=r"^An error_message belongs to an unavailable result$"):
        BranchDriftResult(error_message="something went wrong")


def test_ancestry_needs_a_resolved_commit_and_a_head() -> None:
    with pytest.raises(
        ValueError, match=r"^Ancestry is only measured for an imported commit the clone resolved, against a head$"
    ):
        GitStateFacts(head=None, imported=IMPORTED, imported_resolvable=True, imported_is_ancestor_of_head=True)

    with pytest.raises(
        ValueError, match=r"^Ancestry is only measured for an imported commit the clone resolved, against a head$"
    ):
        GitStateFacts(head=HEAD, imported=IMPORTED, imported_resolvable=False, imported_is_ancestor_of_head=True)

    with pytest.raises(
        ValueError, match=r"^Ancestry is only measured for an imported commit the clone resolved, against a head$"
    ):
        GitStateFacts(head=HEAD, imported=IMPORTED, imported_is_ancestor_of_head=True)


def test_a_pending_count_needs_the_imported_commit_to_be_an_ancestor() -> None:
    with pytest.raises(
        ValueError, match=r"^A pending count is only measured when the imported commit is an ancestor of the head$"
    ):
        GitStateFacts(
            head=HEAD,
            imported=IMPORTED,
            imported_resolvable=True,
            imported_is_ancestor_of_head=False,
            pending_count=2,
        )


def test_the_measurable_fact_shapes_are_accepted() -> None:
    behind = GitStateFacts(
        head=HEAD,
        imported=IMPORTED,
        imported_resolvable=True,
        imported_is_ancestor_of_head=True,
        pending_count=2,
    )
    orphaned = GitStateFacts(head=HEAD, imported=IMPORTED, imported_resolvable=False)
    no_remote = GitStateFacts(head=None, imported=IMPORTED, imported_resolvable=True)
    behind_uncounted = GitStateFacts(
        head=HEAD, imported=IMPORTED, imported_resolvable=True, imported_is_ancestor_of_head=True
    )

    assert behind.pending_count == 2
    assert orphaned.imported_is_ancestor_of_head is None
    assert no_remote.imported_is_ancestor_of_head is None
    assert behind_uncounted.pending_count is None


def test_a_commit_summary_is_the_first_line_whatever_the_line_ending() -> None:
    crlf = CommitEntry(
        hash=HEAD,
        message="Add a widget\r\n\r\nWith a body.\r\n",
        author_name="Ada Lovelace",
        authored_at=datetime(2026, 9, 8, 10, 30, tzinfo=UTC),
        committed_at=datetime(2026, 9, 8, 10, 30, tzinfo=UTC),
        state=RepositoryCommitState.HEAD,
    )
    empty = CommitEntry(
        hash=HEAD,
        message="",
        author_name="Ada Lovelace",
        authored_at=datetime(2026, 9, 8, 10, 30, tzinfo=UTC),
        committed_at=datetime(2026, 9, 8, 10, 30, tzinfo=UTC),
        state=RepositoryCommitState.HEAD,
    )

    assert crlf.summary == "Add a widget"
    assert crlf.short_hash == "3333333"
    assert not empty.summary
