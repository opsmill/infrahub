from __future__ import annotations

import re
from dataclasses import dataclass

import pytest

from infrahub.core.preferences.validation import normalize_timezone
from infrahub.exceptions import ValidationError


@dataclass
class NormalizeCase:
    name: str
    value: str | None
    expected: str | None


NORMALIZE_CASES = [
    NormalizeCase(name="iana_region_city", value="Asia/Tokyo", expected="Asia/Tokyo"),
    NormalizeCase(name="iana_europe", value="Europe/Paris", expected="Europe/Paris"),
    NormalizeCase(name="utc", value="UTC", expected="UTC"),
    NormalizeCase(name="etc_offset_zone", value="Etc/GMT+5", expected="Etc/GMT+5"),
    NormalizeCase(name="empty_string_is_unset", value="", expected=None),
    NormalizeCase(name="none_is_unset", value=None, expected=None),
]


@pytest.mark.parametrize("case", NORMALIZE_CASES, ids=lambda case: case.name)
def test_normalize_timezone_accepts_and_normalizes(case: NormalizeCase) -> None:
    assert normalize_timezone(case.value) == case.expected


@dataclass
class RejectCase:
    name: str
    value: str


REJECT_CASES = [
    RejectCase(name="unknown_zone", value="Not/AZone"),
    RejectCase(name="offset_is_not_a_zone", value="UTC+25"),
    RejectCase(name="injection_string", value="'; DROP TABLE--"),
    RejectCase(name="overlong_string", value="A" * 300),
    RejectCase(name="localtime_pseudo_zone", value="localtime"),
    RejectCase(name="posix_implementation_key", value="posix/UTC"),
    RejectCase(name="right_implementation_key", value="right/UTC"),
]


@pytest.mark.parametrize("case", REJECT_CASES, ids=lambda case: case.name)
def test_normalize_timezone_rejects_non_iana(case: RejectCase) -> None:
    expected = f"'{case.value}' is not a valid IANA timezone"
    with pytest.raises(ValidationError, match=rf"^{re.escape(expected)}$"):
        normalize_timezone(case.value)
