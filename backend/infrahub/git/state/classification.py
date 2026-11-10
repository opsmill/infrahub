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

    An imported commit the clone cannot resolve is ORPHANED whatever else was measured, and a
    configured ref with no head is REF_MISSING even when nothing is imported.
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
    commit_hash: str, is_pending: bool, facts: GitStateFacts, condition: RepositoryGitCondition
) -> RepositoryCommitState:
    """Return the state of one listed commit.

    ``is_pending`` says whether the commit is reachable from the head but not from the imported
    commit. Under a condition unrelated to the imported commit, every commit but the head is
    UNRELATED, since a rewritten ref shares ancestors that must not read as imported.
    """
    if condition in CONDITIONS_UNRELATED_TO_IMPORTED:
        return RepositoryCommitState.HEAD if commit_hash == facts.head else RepositoryCommitState.UNRELATED
    if commit_hash == facts.imported:
        return RepositoryCommitState.IMPORTED
    if commit_hash == facts.head:
        return RepositoryCommitState.HEAD
    return RepositoryCommitState.PENDING if is_pending else RepositoryCommitState.HISTORY
