"""Classify what a worker measured on its clone. Pure: no git, no I/O."""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import RepositoryCommitState, RepositoryGitCondition

if TYPE_CHECKING:
    from .models import GitStateFacts

CONDITIONS_UNRELATED_TO_IMPORTED = frozenset(
    {RepositoryGitCondition.REWRITTEN, RepositoryGitCondition.ORPHANED, RepositoryGitCondition.NOT_TRACKED}
)
"""Conditions under which no listed commit can be placed relative to the imported commit."""


def classify(facts: GitStateFacts) -> RepositoryGitCondition:
    """Return how the remote head relates to the imported commit.

    An imported hash the clone cannot resolve is decided first, so no ancestry answer is ever
    consulted for it. A configured ref with no head is an error to act on, so it is decided before
    a branch that merely has nothing imported.
    """
    if facts.imported is not None and facts.imported_resolvable is False:
        return RepositoryGitCondition.ORPHANED
    if facts.head is None:
        if facts.ref_is_configured:
            return RepositoryGitCondition.REF_MISSING
        return RepositoryGitCondition.NOT_TRACKED if facts.imported is None else RepositoryGitCondition.NO_REMOTE
    if facts.imported is None:
        return RepositoryGitCondition.NOT_TRACKED
    if facts.head == facts.imported:
        return RepositoryGitCondition.IN_SYNC
    return RepositoryGitCondition.BEHIND if facts.imported_is_ancestor_of_head else RepositoryGitCondition.REWRITTEN


def classify_commit(
    hash: str,  # noqa: A002
    is_pending: bool,
    facts: GitStateFacts,
    condition: RepositoryGitCondition,
) -> RepositoryCommitState:
    """Return the state of one listed commit.

    ``is_pending`` says whether the commit is reachable from the head but not from the imported
    commit. The condition decides first: a rewritten ref usually shares most of its history with the
    old one, and those shared ancestors must not read as already imported.
    """
    if condition in CONDITIONS_UNRELATED_TO_IMPORTED:
        return RepositoryCommitState.HEAD if hash == facts.head else RepositoryCommitState.UNRELATED
    if hash == facts.imported:
        return RepositoryCommitState.IMPORTED
    if hash == facts.head:
        return RepositoryCommitState.HEAD
    return RepositoryCommitState.PENDING if is_pending else RepositoryCommitState.HISTORY
