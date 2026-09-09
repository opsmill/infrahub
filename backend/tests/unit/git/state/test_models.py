from __future__ import annotations

import pytest

from infrahub.core.constants import RepositoryGitCondition, RepositoryGitUnavailableReason
from infrahub.git.state.models import CommitLogResult


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
