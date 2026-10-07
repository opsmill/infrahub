from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True, kw_only=True)
class NumberSpan:
    """An inclusive span of numbers."""

    start: int
    end: int

    def __post_init__(self) -> None:
        """Refuse a span whose end precedes its start.

        Raises:
            ValueError: If `end` is lower than `start`.

        """
        if self.end < self.start:
            raise ValueError(
                f"Span end ({self.end}) is lower than its start ({self.start}); a span runs upward from start to end."
            )

    @property
    def size(self) -> int:
        return self.end - self.start + 1


@dataclass(frozen=True, kw_only=True)
class NumberDomain:
    """The numbers an attribute accepts: optional inclusive bounds and excluded inclusive spans, which may overlap."""

    lower: int | None = None
    upper: int | None = None
    exclusions: tuple[NumberSpan, ...] = ()

    def carve(self, start: int, end: int) -> list[NumberSpan]:
        """Return the spans of `[start, end]` the domain accepts, in ascending order."""
        if self.lower is not None:
            start = max(start, self.lower)
        if self.upper is not None:
            end = min(end, self.upper)

        accepted: list[NumberSpan] = []
        cursor = start
        for excluded in sorted(self.exclusions, key=lambda span: span.start):
            if cursor > end or excluded.start > end:
                break
            if excluded.end < cursor:
                continue
            if excluded.start > cursor:
                accepted.append(NumberSpan(start=cursor, end=excluded.start - 1))
            cursor = excluded.end + 1
        if cursor <= end:
            accepted.append(NumberSpan(start=cursor, end=end))
        return accepted


@dataclass(frozen=True, kw_only=True)
class EffectiveSegment(NumberSpan):
    """An inclusive span of allocatable numbers carved out of one pool range."""

    range_id: str


@dataclass(frozen=True, kw_only=True)
class PoolRange(NumberSpan):
    """An inclusive span of numbers a pool allocates from, with its allocation weight."""

    weight: int = 0
    id: str

    def segments_in(self, domain: NumberDomain) -> list[EffectiveSegment]:
        """Return the parts of this range the domain accepts, in ascending order."""
        return [
            EffectiveSegment(start=span.start, end=span.end, range_id=self.id)
            for span in domain.carve(self.start, self.end)
        ]


class EffectiveSpace:
    """The numbers a pool can hand out: its ranges carved by the domain of the attribute it feeds.

    The ranges must not overlap one another, so that one segment at most holds any number.
    Segments come in allocation order: higher weight first, then lower range start, then ascending inside a range.
    """

    def __init__(self, ranges: Sequence[PoolRange], domain: NumberDomain) -> None:
        self._ranges = tuple(ranges)
        self._domain = domain

    @cached_property
    def segments(self) -> tuple[EffectiveSegment, ...]:
        ordered = sorted(self._ranges, key=lambda pool_range: (-pool_range.weight, pool_range.start, pool_range.end))
        return tuple(segment for pool_range in ordered for segment in pool_range.segments_in(self._domain))

    @cached_property
    def size(self) -> int:
        return sum(segment.size for segment in self.segments)

    @property
    def is_empty(self) -> bool:
        return self.size == 0

    def as_query_ranges(self) -> list[list[int]]:
        """Return the segments as `[start, end]` pairs in allocation order."""
        return [[segment.start, segment.end] for segment in self.segments]

    def contains(self, value: int) -> bool:
        return self._segment_holding(value) is not None

    def range_for(self, value: int) -> str | None:
        """Return the id of the range whose segment holds `value`, or None when no segment holds it."""
        segment = self._segment_holding(value)
        return segment.range_id if segment else None

    def segments_of(self, range_id: str) -> tuple[EffectiveSegment, ...]:
        return self._by_range.get(range_id, ())

    def size_of(self, range_id: str) -> int:
        """Return how many numbers the range contributes to the space, 0 for a range it does not hold."""
        return sum(segment.size for segment in self.segments_of(range_id))

    @cached_property
    def _by_range(self) -> dict[str, tuple[EffectiveSegment, ...]]:
        by_range: dict[str, list[EffectiveSegment]] = {}
        for segment in self.segments:
            by_range.setdefault(segment.range_id, []).append(segment)
        return {range_id: tuple(segments) for range_id, segments in by_range.items()}

    @cached_property
    def _by_start(self) -> tuple[EffectiveSegment, ...]:
        return tuple(sorted(self.segments, key=lambda segment: segment.start))

    @cached_property
    def _starts(self) -> tuple[int, ...]:
        return tuple(segment.start for segment in self._by_start)

    def _segment_holding(self, value: int) -> EffectiveSegment | None:
        index = bisect_right(self._starts, value) - 1
        if index < 0:
            return None
        segment = self._by_start[index]
        return segment if value <= segment.end else None
