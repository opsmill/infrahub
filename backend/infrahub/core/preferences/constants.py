from __future__ import annotations

from infrahub.utils import InfrahubStringEnum


class DateFormat(InfrahubStringEnum):
    """Semantic date-format keys clients map to their own formatter."""

    ISO_8601 = "ISO_8601"  # 2026-07-01T14:30:00+02:00
    ISO_DATETIME = "ISO_DATETIME"  # 2026-07-01 14:30
    ISO_DATETIME_SECONDS = "ISO_DATETIME_SECONDS"  # 2026-07-01 14:30:00
    EU_DATETIME = "EU_DATETIME"  # 01/07/2026 14:30
    US_12H = "US_12H"  # 07/01/2026 02:30 PM


class PreferenceSource(InfrahubStringEnum):
    """Which layer an effective preference value was resolved from."""

    USER = "user"
    GLOBAL = "global"
    DEFAULT = "default"


# Default date-format key applied when neither the user nor the global layer sets one.
DEFAULT_DATE_FORMAT = DateFormat.ISO_DATETIME
