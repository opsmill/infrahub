from __future__ import annotations

from datetime import UTC, datetime

import pytest

from infrahub.core.preferences import DATE_FORMAT_KEYS, DEFAULT_DATE_FORMAT, render_datetime
from infrahub.core.preferences.formats import DATE_FORMAT_STRFTIME

# A fixed, timezone-aware reference instant so every expected rendering is deterministic.
_REFERENCE = datetime(2026, 7, 1, 14, 30, 0, tzinfo=UTC)


def test_default_is_a_known_key() -> None:
    # The fallback key must itself be renderable, else render_datetime would recurse into nothing.
    assert DEFAULT_DATE_FORMAT in DATE_FORMAT_STRFTIME


def test_keys_and_render_map_never_drift() -> None:
    # DATE_FORMAT_KEYS (which the GraphQL DateFormat enum is built from) is exactly the render map.
    assert set(DATE_FORMAT_KEYS) == set(DATE_FORMAT_STRFTIME)


@pytest.mark.parametrize(
    ("date_format", "expected"),
    [
        ("ISO_8601", "2026-07-01T14:30:00+0000"),
        ("ISO_DATETIME", "2026-07-01 14:30"),
        ("ISO_DATETIME_SECONDS", "2026-07-01 14:30:00"),
        ("EU_DATETIME", "01/07/2026 14:30"),
        ("US_12H", "07/01/2026 02:30 PM"),
    ],
)
def test_render_datetime_known_keys(date_format: str, expected: str) -> None:
    assert render_datetime(_REFERENCE, date_format) == expected


def test_render_datetime_none_falls_back_to_default() -> None:
    assert render_datetime(_REFERENCE, None) == render_datetime(_REFERENCE, DEFAULT_DATE_FORMAT)


def test_render_datetime_unknown_key_falls_back_to_default() -> None:
    # A value written before a key was retired (or by an out-of-date client) still renders.
    assert render_datetime(_REFERENCE, "RETIRED_FORMAT") == render_datetime(_REFERENCE, DEFAULT_DATE_FORMAT)
