from __future__ import annotations

import re
from dataclasses import dataclass

import pytest

from infrahub.exceptions import ValidationError
from infrahub.instance_identity import validate_instance_label


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
    LabelNormalizeCase(name="emoji_is_kept", value="PROD 🚀", expected="PROD 🚀"),
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
        expected_message="instance_label cannot contain control characters",
    ),
    LabelRejectCase(
        name="carriage_return",
        value="a\rb",
        expected_message="instance_label cannot contain control characters",
    ),
    LabelRejectCase(
        name="tab",
        value="a\tb",
        expected_message="instance_label cannot contain control characters",
    ),
    LabelRejectCase(
        name="nul",
        value="a\x00b",
        expected_message="instance_label cannot contain control characters",
    ),
    LabelRejectCase(
        name="unicode_line_separator",
        value="a\u2028b",
        expected_message="instance_label cannot contain control characters",
    ),
    LabelRejectCase(
        name="unicode_paragraph_separator",
        value="a\u2029b",
        expected_message="instance_label cannot contain control characters",
    ),
    LabelRejectCase(
        name="bidi_override",
        value="a\u202eb",
        expected_message="instance_label cannot contain control characters",
    ),
    LabelRejectCase(
        name="bidi_isolate",
        value="a\u2066b",
        expected_message="instance_label cannot contain control characters",
    ),
    LabelRejectCase(
        name="right_to_left_mark",
        value="a\u200fb",
        expected_message="instance_label cannot contain control characters",
    ),
]


@pytest.mark.parametrize("case", LABEL_REJECT_CASES, ids=lambda case: case.name)
def test_validate_instance_label_rejects(case: LabelRejectCase) -> None:
    with pytest.raises(ValidationError, match=rf"^{re.escape(case.expected_message)}$"):
        validate_instance_label(case.value)
