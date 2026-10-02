from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RefClassification(StrEnum):
    UNCHANGED = "unchanged"
    FAST_FORWARD = "fast-forward"
    REWRITE = "rewrite"
    RETARGET = "retarget"
    REMOTE_ABSENT = "remote-absent"


ALLOWED_WITHOUT_IMPORTED_COMMIT = frozenset({RefClassification.UNCHANGED, RefClassification.FAST_FORWARD})
ALLOWED_WITHOUT_REMOTE_HEAD = frozenset({RefClassification.REMOTE_ABSENT, RefClassification.UNCHANGED})


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
        if self.imported_commit is None and self.classification not in ALLOWED_WITHOUT_IMPORTED_COMMIT:
            raise ValueError(f"A branch with no imported commit cannot be {self.classification}")
        if self.remote_head is None:
            if self.classification not in ALLOWED_WITHOUT_REMOTE_HEAD:
                raise ValueError(f"A branch with no remote head cannot be {self.classification}")
            if self.classification is RefClassification.UNCHANGED and self.imported_commit is not None:
                raise ValueError("An imported branch whose remote head is gone is REMOTE_ABSENT, not UNCHANGED")


@dataclass(frozen=True)
class ReconciledBranch:
    """One branch a synchronisation cycle advanced, and the commit it advanced to."""

    infrahub_branch_name: str
    infrahub_branch_id: str
    """The branch UUID, not the database element id."""

    commit: str
    divergence: RefDivergence | None = None
    """Set when the branch was reconciled from a rewrite, None for an ordinary fast-forward."""
