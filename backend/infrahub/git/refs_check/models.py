"""What a refs check and a refs-check cycle report when they are done."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True)
class RefMovement:
    """A tracked ref whose remote head no longer matches the local view of it."""

    ref: str

    previous_head: str | None
    """What this worker's copy resolved the ref to, absent when it held no such ref."""

    new_head: str

    def __post_init__(self) -> None:
        if self.previous_head == self.new_head:
            raise ValueError(f"Ref '{self.ref}' has not moved, both heads are {self.new_head}")


class RefsCheckOutcome(StrEnum):
    COMPLETED = "completed"
    """The remote was listed; ``movements`` says whether anything had moved."""

    SKIPPED_CLAIMED = "skipped_claimed"
    """Another run held the repository, so this one did no remote work."""

    FAILED = "failed"
    """The check could not be carried out; ``failure_reason`` says why."""


@dataclass(frozen=True)
class RefsCheckResult:
    """What one repository's check did, in a shape that cannot describe two things at once."""

    repository_id: str
    repository_name: str
    outcome: RefsCheckOutcome
    claimed_by: str | None = None
    """The run already holding the repository, when this one did not get the claim."""

    movements: tuple[RefMovement, ...] = ()
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if self.movements and self.outcome is not RefsCheckOutcome.COMPLETED:
            raise ValueError(f"A {self.outcome} check cannot carry movements")
        if (self.failure_reason is not None) != (self.outcome is RefsCheckOutcome.FAILED):
            raise ValueError(f"A {self.outcome} check must carry a failure reason if and only if it failed")
        if (self.claimed_by is not None) and self.outcome is not RefsCheckOutcome.SKIPPED_CLAIMED:
            raise ValueError(f"A {self.outcome} check cannot name the run that holds the claim")

    @property
    def moved(self) -> bool:
        return bool(self.movements)

    @property
    def failed(self) -> bool:
        return self.outcome is RefsCheckOutcome.FAILED

    @property
    def contacted_remote(self) -> bool:
        return self.outcome is not RefsCheckOutcome.SKIPPED_CLAIMED


@dataclass(frozen=True)
class RefsCheckCycleSummary:
    """What one scheduled cycle did.

    Every count is derived from ``results``, so no two of them can disagree.
    """

    results: tuple[RefsCheckResult, ...]

    not_due: int
    """Repositories passed over because their last check is still within the interval."""

    duration_seconds: float

    @property
    def checked_count(self) -> int:
        """Repositories whose remote this cycle actually tried to read."""
        return sum(1 for result in self.results if result.contacted_remote)

    @property
    def moved_count(self) -> int:
        return sum(1 for result in self.results if result.moved)

    @property
    def failed_count(self) -> int:
        return sum(1 for result in self.results if result.failed)

    @property
    def claimed_elsewhere_count(self) -> int:
        return sum(1 for result in self.results if result.outcome is RefsCheckOutcome.SKIPPED_CLAIMED)
