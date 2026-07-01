from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

# Canonical date-format preset keys (INFP-512). The stored `date_format` preference is one of these
# SEMANTIC keys, not a library-specific pattern, so every client maps the key to its own renderer:
# the web app via date-fns, the backend via strftime (below), a future SDK via its own. Adding a
# format is one entry here plus the frontend's key->date-fns map; StandardNode stores the key
# string, so there is no schema or migration change.
#
# The set is deliberately limited to formats that render identically and trivially on every client
# (plain strftime, no locale library, no ambiguity). Locale-dependent or relative modes were left
# out for exactly that reason — see dev/specs/2026-04-user-preferences.md.
DATE_FORMAT_STRFTIME: dict[str, str] = {
    "ISO_8601": "%Y-%m-%dT%H:%M:%S%z",  # 2026-07-01T14:30:00+02:00
    "ISO_DATETIME": "%Y-%m-%d %H:%M",  # 2026-07-01 14:30
    "ISO_DATETIME_SECONDS": "%Y-%m-%d %H:%M:%S",  # 2026-07-01 14:30:00
    "EU_DATETIME": "%d/%m/%Y %H:%M",  # 01/07/2026 14:30
    "US_12H": "%m/%d/%Y %I:%M %p",  # 07/01/2026 02:30 PM
}

# Applied when neither the user nor the global singleton has set date_format. Kept in sync with the
# frontend default (same key) so a date the backend renders matches what the UI would show.
DEFAULT_DATE_FORMAT = "ISO_DATETIME"

# Valid semantic keys in display order. The GraphQL `DateFormat` enum is built from this tuple so
# the enum and the render map can never drift apart.
DATE_FORMAT_KEYS: tuple[str, ...] = tuple(DATE_FORMAT_STRFTIME)


def render_datetime(value: datetime, date_format: str | None) -> str:
    """Render a datetime using a semantic date-format key, falling back to the default.

    A None or unknown key falls back to DEFAULT_DATE_FORMAT rather than raising, so a value stored
    before a key was retired (or written by an out-of-date client) still renders sensibly.
    """
    pattern = DATE_FORMAT_STRFTIME.get(date_format or DEFAULT_DATE_FORMAT) or DATE_FORMAT_STRFTIME[DEFAULT_DATE_FORMAT]
    return value.strftime(pattern)
