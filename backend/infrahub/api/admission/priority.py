from __future__ import annotations

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
