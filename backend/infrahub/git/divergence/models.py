from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


class RefClassification(StrEnum):
    UNCHANGED = "unchanged"
    FAST_FORWARD = "fast-forward"
    REWRITE = "rewrite"
    RETARGET = "retarget"
    REMOTE_ABSENT = "remote-absent"


@dataclass(frozen=True)
class RefDivergence:
    """What one classification decided for one tracked ref."""

    branch_name: str
    """The remote branch, or the tracked ref of a read-only repository."""

    infrahub_branch_name: str
    imported_commit: str | None
    """The commit recorded in the graph, never the local worktree head."""

    remote_head: str | None
    classification: RefClassification

    def __post_init__(self) -> None:
        if self.imported_commit is None and self.classification not in (
            RefClassification.UNCHANGED,
            RefClassification.FAST_FORWARD,
        ):
            raise ValueError(f"A branch with no imported commit cannot be {self.classification}")
        if self.remote_head is None and self.classification not in (
            RefClassification.REMOTE_ABSENT,
            RefClassification.UNCHANGED,
        ):
            raise ValueError(f"A branch with no remote head cannot be {self.classification}")
        if self.remote_head is not None and self.classification is RefClassification.REMOTE_ABSENT:
            raise ValueError(f"A branch whose remote head reads {self.remote_head} is not remote-absent")

        # Nothing moved and something moved are the same question asked twice, so the two commits
        # matching decides unchanged on its own.
        commits_match = self.imported_commit == self.remote_head
        if commits_match and self.classification is not RefClassification.UNCHANGED:
            raise ValueError(
                f"A branch whose commits both read {self.remote_head} is unchanged, not {self.classification}"
            )
        if not commits_match and self.classification is RefClassification.UNCHANGED:
            raise ValueError(
                f"A branch is not unchanged when {self.imported_commit} was imported and the remote "
                f"reads {self.remote_head}"
            )

    @property
    def discarded_commit(self) -> str | None:
        """The imported commit when the remote history no longer contains it, None when it still does."""
        if self.classification in (RefClassification.REWRITE, RefClassification.RETARGET):
            return self.imported_commit
        return None


@dataclass(frozen=True)
class ReconciledBranch:
    """One branch a synchronisation cycle advanced, and the commit it advanced to."""

    infrahub_branch_name: str
    """The branch whose commit the cycle wrote.

    For a staging repository it is the branch the trunk maps onto, not the staging branch that receives
    the objects.
    """

    infrahub_branch_id: str
    """The branch UUID, not the database element id."""

    commit: str
    divergence: RefDivergence | None = None
    """How the remote head compares to the commit the graph recorded, None when no graph commit was given."""


@dataclass(frozen=True)
class TrackedTarget:
    """The ref and the commit a read-only repository records on one Infrahub branch."""

    ref: str
    commit: str | None
    """None when the branch records no full commit id."""


@dataclass(frozen=True)
class RewriteRecord:
    """What the repository holds about the last history rewrite of one branch."""

    previous_commit: str
    """The commit the graph recorded before the rewrite."""

    commit: str
    """The commit the branch was reconciled onto."""

    rewritten_at: datetime
    rewrite_count: int
    """The rewrites the branch reads, including those of the branch it was created from."""
