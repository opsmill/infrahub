from __future__ import annotations

from infrahub.utils import InfrahubStringEnum


class DateFormat(InfrahubStringEnum):
    """Semantic date-format keys.

    Each value is a key that clients map to their own formatter, NOT a rendering pattern. The set is
    deliberately limited to formats that render identically on every client (no locale library, no
    relative mode). Member name == value so the API enum literal, the stored string, and the client
    key all coincide.
    """

    ISO_8601 = "ISO_8601"  # 2026-07-01T14:30:00+02:00
    ISO_DATETIME = "ISO_DATETIME"  # 2026-07-01 14:30
    ISO_DATETIME_SECONDS = "ISO_DATETIME_SECONDS"  # 2026-07-01 14:30:00
    EU_DATETIME = "EU_DATETIME"  # 01/07/2026 14:30
    US_12H = "US_12H"  # 07/01/2026 02:30 PM


class PreferenceSource(InfrahubStringEnum):
    """Where an effective preference value came from.

    USER    = the caller's own override.
    GLOBAL  = the organisation-wide default.
    DEFAULT = nothing is stored anywhere; the client applies its built-in default.
    """

    USER = "user"
    GLOBAL = "global"
    DEFAULT = "default"


# The key a client applies when neither the user nor the global preference sets date_format. The
# backend does not render dates itself (clients do), so this is exposed only as the shared default
# key both sides agree on; it is intentionally not used to produce a server-side rendered string.
DEFAULT_DATE_FORMAT = DateFormat.ISO_DATETIME
