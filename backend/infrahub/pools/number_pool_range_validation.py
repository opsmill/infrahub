from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from infrahub.exceptions import ValidationError
from infrahub.pools.number_ranges import OPEN_END, OPEN_START, NumberDomain, format_range_label

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable


@dataclass(frozen=True)
class NumberRangeBounds:
    """The inclusive bounds of a number pool range, None for an open bound, and the range's id once it is stored."""

    start: int | None
    end: int | None
    id: str | None = None

    @property
    def lower(self) -> int:
        return OPEN_START if self.start is None else self.start

    @property
    def upper(self) -> int:
        return OPEN_END if self.end is None else self.end

    def label(self, domain: NumberDomain) -> str:
        """Return the bounds as "start - end", reading an open bound through the domain's min_value and max_value."""
        start, end = domain.resolve(start=self.start, end=self.end)
        return format_range_label(start=start, end=end)

    def overlaps(self, other: NumberRangeBounds) -> bool:
        return self.lower <= other.upper and other.lower <= self.upper


@dataclass(frozen=True)
class RangeLimitViolation:
    """A range reaching outside the min_value or max_value of the attribute its pool allocates for."""

    bounds: NumberRangeBounds
    field_name: Literal["start", "end"]
    message: str


def validate_number_pool_range(
    candidate: NumberRangeBounds, others: Iterable[NumberRangeBounds], domain: NumberDomain
) -> None:
    """Refuse a range whose end is below its start, or that overlaps another range of the same pool.

    Args:
        candidate: The range being saved.
        others: The pool's ranges; an entry carrying the candidate's id is the candidate itself and is skipped.
        domain: The numbers the pool's attribute accepts, which the messages read open bounds through.

    Raises:
        ValidationError: When the candidate is backwards, or overlaps one or more of the other ranges, which
            the message lists by bounds and id.

    """
    if candidate.upper < candidate.lower:
        raise ValidationError(
            input_value=f"Range end ({candidate.upper}) cannot be lower than start ({candidate.lower})"
        )

    clashes = sorted(
        (other for other in others if other.id != candidate.id and candidate.overlaps(other)),
        key=lambda other: (other.lower, other.upper),
    )
    if clashes:
        clash_labels = ", ".join(f"{clash.label(domain)} ({clash.id})" for clash in clashes)
        raise ValidationError(input_value=f"Range {candidate.label(domain)} overlaps {clash_labels}")


def validate_number_pool_ranges(ranges: Collection[NumberRangeBounds], domain: NumberDomain) -> None:
    """Refuse a pool's range set when one of its ranges is backwards or overlaps another.

    Raises:
        ValidationError: For the lowest offending range, naming the ranges it overlaps.

    """
    for candidate in sorted(ranges, key=lambda pool_range: (pool_range.lower, pool_range.upper)):
        validate_number_pool_range(candidate=candidate, others=ranges, domain=domain)


def find_ranges_outside_attribute(
    ranges: Collection[NumberRangeBounds], domain: NumberDomain
) -> list[RangeLimitViolation]:
    """Return every range reaching outside the attribute's min_value or max_value, lowest range first.

    An entered start must not be below min_value and an entered end must not be above max_value. An open end follows
    max_value, so its range is refused only when its start is above max_value; an open start follows min_value, so its
    range is refused only when its end is below min_value.
    """
    min_value, max_value = domain.lower, domain.upper
    violations: list[RangeLimitViolation] = []
    for candidate in sorted(ranges, key=lambda pool_range: (pool_range.lower, pool_range.upper)):
        start, end = candidate.start, candidate.end
        if min_value is not None and start is not None and start < min_value:
            violations.append(
                RangeLimitViolation(
                    bounds=candidate,
                    field_name="start",
                    message=f"Range {candidate.label(domain)} starts below the attribute's min_value ({min_value})",
                )
            )
        if max_value is not None and end is not None and end > max_value:
            violations.append(
                RangeLimitViolation(
                    bounds=candidate,
                    field_name="end",
                    message=f"Range {candidate.label(domain)} ends above the attribute's max_value ({max_value})",
                )
            )
        if max_value is not None and end is None and start is not None and start > max_value:
            violations.append(
                RangeLimitViolation(
                    bounds=candidate,
                    field_name="start",
                    message=f"Range starting at {start} without an end starts above the attribute's max_value ({max_value})",
                )
            )
        if min_value is not None and start is None and end is not None and end < min_value:
            violations.append(
                RangeLimitViolation(
                    bounds=candidate,
                    field_name="end",
                    message=f"Range ending at {end} without a start ends below the attribute's min_value ({min_value})",
                )
            )
    return violations


def validate_ranges_within_attribute(ranges: Collection[NumberRangeBounds], domain: NumberDomain) -> None:
    """Refuse ranges reaching outside the min_value or max_value of the attribute the pool allocates for.

    Raises:
        ValidationError: For the lowest offending range.

    """
    violations = find_ranges_outside_attribute(ranges=ranges, domain=domain)
    if violations:
        raise ValidationError(input_value=violations[0].message)


def validate_shorthand_target(ranges: Collection[NumberRangeBounds], domain: NumberDomain) -> None:
    """Refuse the single-range start/end shorthand on a pool holding more than one range.

    Raises:
        ValidationError: Listing every range of the pool by bounds and id.

    """
    if len(ranges) <= 1:
        return
    range_labels = ", ".join(
        f"{pool_range.label(domain)} ({pool_range.id})"
        for pool_range in sorted(ranges, key=lambda pool_range: (pool_range.lower, pool_range.upper))
    )
    raise ValidationError(
        input_value=(
            "start_range/end_range apply to a pool holding at most one range; "
            f"this pool holds: {range_labels}. Edit the ranges instead."
        )
    )
