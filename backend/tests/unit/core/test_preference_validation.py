from __future__ import annotations

import re
from dataclasses import dataclass

import pytest

from infrahub.core.preferences.validation import validate_instance_label, validate_timezone
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
def test_validate_timezone_accepts_and_normalizes(case: NormalizeCase) -> None:
    assert validate_timezone(case.value) == case.expected


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
    RejectCase(name="posixrules_pseudo_zone", value="posixrules"),
    RejectCase(name="posix_implementation_key", value="posix/UTC"),
    RejectCase(name="right_implementation_key", value="right/UTC"),
]


@pytest.mark.parametrize("case", REJECT_CASES, ids=lambda case: case.name)
def test_validate_timezone_rejects_non_iana(case: RejectCase) -> None:
    expected = f"'{case.value}' is not a valid IANA timezone"
    with pytest.raises(ValidationError, match=rf"^{re.escape(expected)}$"):
        validate_timezone(case.value)


@dataclass
class LabelNormalizeCase:
    name: str
    value: str | None
    expected: str | None


LABEL_NORMALIZE_CASES: list[LabelNormalizeCase] = [
    LabelNormalizeCase(name="surrounding_whitespace_is_stripped", value="  QA  ", expected="QA"),
    LabelNormalizeCase(name="empty_string_is_unset", value="", expected=None),
    LabelNormalizeCase(name="whitespace_only_is_unset", value="   ", expected=None),
    LabelNormalizeCase(name="none_is_unset", value=None, expected=None),
    LabelNormalizeCase(name="non_ascii_is_kept", value="Zürich PROD", expected="Zürich PROD"),
    LabelNormalizeCase(name="inner_spaces_are_kept", value="us-east-1 PROD", expected="us-east-1 PROD"),
    LabelNormalizeCase(name="max_length_is_kept", value="a" * 32, expected="a" * 32),
    LabelNormalizeCase(name="whitespace_beyond_max_length_is_stripped", value=" " + "a" * 32 + " ", expected="a" * 32),
]


@pytest.mark.parametrize("case", LABEL_NORMALIZE_CASES, ids=lambda case: case.name)
def test_validate_instance_label_accepts_and_normalizes(case: LabelNormalizeCase) -> None:
    assert validate_instance_label(case.value) == case.expected


@dataclass
class LabelRejectCase:
    name: str
    value: str
    expected_message: str


LABEL_REJECT_CASES: list[LabelRejectCase] = [
    LabelRejectCase(
        name="one_over_max_length",
        value="a" * 33,
        expected_message="instance_label cannot be longer than 32 characters",
    ),
    LabelRejectCase(
        name="line_feed",
        value="a\nb",
        expected_message="instance_label cannot contain a line break",
    ),
    LabelRejectCase(
        name="carriage_return",
        value="a\rb",
        expected_message="instance_label cannot contain a line break",
    ),
]


@pytest.mark.parametrize("case", LABEL_REJECT_CASES, ids=lambda case: case.name)
def test_validate_instance_label_rejects(case: LabelRejectCase) -> None:
    with pytest.raises(ValidationError, match=rf"^{re.escape(case.expected_message)}$"):
        validate_instance_label(case.value)
