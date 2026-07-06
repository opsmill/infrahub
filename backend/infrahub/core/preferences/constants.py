from __future__ import annotations

from infrahub.utils import InfrahubStringEnum


class DateFormat(InfrahubStringEnum):
    """Semantic date-format keys (INFP-512).

    The stored `date_format` preference is one of these keys, NOT a rendering pattern: each client
    maps the key to its own formatter (the web app via date-fns). This Python enum is the single
    source of truth — the GraphQL `DateFormat` enum is derived from it (graphql/types/preferences.py)
    and the `Preference` model validates `date_format` against it, so the stored value is never an
    arbitrary string.

    The set is deliberately limited to formats that render identically on every client (no locale
    library, no relative mode); see dev/specs/2026-04-user-preferences.md. Member name == value so
    the GraphQL enum literal, the stored string, and the frontend key all coincide.
    """

    ISO_8601 = "ISO_8601"  # 2026-07-01T14:30:00+02:00
    ISO_DATETIME = "ISO_DATETIME"  # 2026-07-01 14:30
    ISO_DATETIME_SECONDS = "ISO_DATETIME_SECONDS"  # 2026-07-01 14:30:00
    EU_DATETIME = "EU_DATETIME"  # 01/07/2026 14:30
    US_12H = "US_12H"  # 07/01/2026 02:30 PM


# The key a client applies when neither the user nor the global preference sets date_format. The
# backend does not render dates itself (clients do), so this is exposed only as the shared default
# key both sides agree on; it is intentionally not used to produce a server-side rendered string.
DEFAULT_DATE_FORMAT = DateFormat.ISO_DATETIME
