from __future__ import annotations

import pytest

from infrahub.core.preferences.models import Preference


def test_date_format_rejects_unknown_key() -> None:
    # date_format is enum-typed, so validating a raw payload with a non-DateFormat key must raise.
    # The match is anchored and stops before pydantic's trailing documentation URL, which carries
    # the installed pydantic version.
    with pytest.raises(
        ValueError,
        match=(
            r"^1 validation error for Preference\n"
            r"date_format\n"
            r"  Input should be 'ISO_8601', 'ISO_DATETIME', 'ISO_DATETIME_SECONDS', 'EU_DATETIME' or 'US_12H' "
            r"\[type=enum, input_value='NOPE', input_type=str\]"
        ),
    ):
        Preference.model_validate({"owner_id": "owner-a", "date_format": "NOPE"})


def test_date_format_accepts_valid_key() -> None:
    pref = Preference.model_validate({"owner_id": "owner-a", "date_format": "ISO_DATETIME"})
    assert pref.date_format == "ISO_DATETIME"
