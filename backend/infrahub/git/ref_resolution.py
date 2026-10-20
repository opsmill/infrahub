"""Resolving a revision against the commits a local copy holds."""

from __future__ import annotations

from typing import TYPE_CHECKING

from git.exc import BadName

if TYPE_CHECKING:
    from git import Repo
    from git.objects import Commit


def resolve_commit(repo: Repo, revisions: tuple[str, ...]) -> Commit | None:
    """Return the commit of the first revision the copy can resolve, or None when it resolves none."""
    for revision in revisions:
        try:
            return repo.commit(revision)
        # An unknown name raises BadName and an unknown full hash raises ValueError.
        except (BadName, ValueError):
            continue
    return None


def resolve_pinned_commit(repo: Repo, git_ref: str) -> Commit | None:
    """Return the commit a ref names when the ref is a commit hash, never when it is a name."""
    pinned = resolve_commit(repo=repo, revisions=(git_ref,))
    if pinned is not None and pinned.hexsha.startswith(git_ref.lower()):
        return pinned
    return None
