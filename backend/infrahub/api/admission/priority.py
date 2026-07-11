from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class Priority(IntEnum):
    """Admission priority classes.

    Membership values are ordered so that a lower value means a higher priority:
    numeric comparison therefore yields priority comparison (``HIGH < NORMAL < LOW``).
    """

    HIGH = 0
    NORMAL = 1
    LOW = 2

    @property
    def label(self) -> str:
        """Prometheus ``priority`` label value for this class (``high``/``normal``/``low``)."""
        return self.name.lower()


@dataclass(frozen=True)
class PriorityHeaderParseResult:
    """Outcome of parsing the priority request header.

    Kept distinct from ``Priority`` so adoption can be recorded without a second parse:
    ``was_explicit`` distinguishes a caller-supplied class from the ``NORMAL`` default.
    """

    priority: Priority
    was_explicit: bool


def parse_priority(header_value: str | None) -> PriorityHeaderParseResult:
    """Classify a priority header value into a priority class.

    The match is case-insensitive and ignores surrounding whitespace. A missing, empty,
    whitespace-only, or unrecognized value resolves to ``NORMAL`` with ``was_explicit=False``.
    This never raises.
    """
    if header_value is None:
        return PriorityHeaderParseResult(priority=Priority.NORMAL, was_explicit=False)

    normalized = header_value.strip().lower()
    try:
        priority = Priority[normalized.upper()]
    except KeyError:
        return PriorityHeaderParseResult(priority=Priority.NORMAL, was_explicit=False)

    return PriorityHeaderParseResult(priority=priority, was_explicit=True)
