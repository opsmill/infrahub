from __future__ import annotations

from infrahub.core.preferences import DEFAULT_DATE_FORMAT, DateFormat

# The exact set of semantic DateFormat keys the backend supports (member name == value). This is the
# single source of truth the GraphQL enum is derived from, so it must not drift silently.
_EXPECTED_KEYS = {
    "ISO_8601",
    "ISO_DATETIME",
    "ISO_DATETIME_SECONDS",
    "EU_DATETIME",
    "US_12H",
}


def test_date_format_has_exactly_the_expected_members() -> None:
    assert {member.value for member in DateFormat} == _EXPECTED_KEYS


def test_date_format_member_name_equals_value() -> None:
    # Name == value so the GraphQL enum literal, the stored string, and the frontend key all coincide.
    for member in DateFormat:
        assert member.name == member.value


def test_default_date_format_is_a_member() -> None:
    assert DEFAULT_DATE_FORMAT in DateFormat
    assert isinstance(DEFAULT_DATE_FORMAT, DateFormat)
