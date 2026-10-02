from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from infrahub.exceptions import ValidationError

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(frozen=True)
class NumberRangeBounds:
    """The inclusive bounds of a number pool range, and the range's id once it is stored."""

    start: int
    end: int
    id: str | None = None

    @property
    def label(self) -> str:
        return f"{self.start}-{self.end}"

    def overlaps(self, other: NumberRangeBounds) -> bool:
        return self.start <= other.end and other.start <= self.end


def validate_number_pool_range(candidate: NumberRangeBounds, others: Iterable[NumberRangeBounds]) -> None:
    """Refuse a range whose end is below its start, or that overlaps another range of the same pool.

    Args:
        candidate: The range being saved.
        others: The pool's ranges; an entry carrying the candidate's id is the candidate itself and is skipped.

    Raises:
        ValidationError: When the candidate is backwards, or overlaps one or more of the other ranges, which
            the message lists by bounds and id.

    """
    if candidate.end < candidate.start:
        raise ValidationError(input_value=f"Range end ({candidate.end}) cannot be lower than start ({candidate.start})")

    clashes = sorted(
        (other for other in others if other.id != candidate.id and candidate.overlaps(other)),
        key=lambda other: (other.start, other.end),
    )
    if clashes:
        clash_labels = ", ".join(f"{clash.label} ({clash.id})" for clash in clashes)
        raise ValidationError(input_value=f"Range {candidate.label} overlaps {clash_labels}")
