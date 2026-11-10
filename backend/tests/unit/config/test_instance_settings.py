from __future__ import annotations

import re
from dataclasses import dataclass

import pytest
from pydantic import ValidationError

from infrahub.config import InstanceSettings
from infrahub.instance_identity import InstanceColor


@dataclass
class AcceptCase:
    name: str
    label: str | None
    color: str | None
    expected_label: str | None
    expected_color: InstanceColor | None


ACCEPT_CASES: list[AcceptCase] = [
    AcceptCase(name="label_and_color", label="QA", color="RED", expected_label="QA", expected_color=InstanceColor.RED),
    AcceptCase(
        name="label_is_trimmed",
        label="  us-east-1 PROD  ",
        color=None,
        expected_label="us-east-1 PROD",
        expected_color=None,
    ),
    AcceptCase(name="empty_label_is_unset", label="", color=None, expected_label=None, expected_color=None),
    AcceptCase(name="whitespace_label_is_unset", label="   ", color=None, expected_label=None, expected_color=None),
    AcceptCase(name="max_length_label", label="a" * 32, color=None, expected_label="a" * 32, expected_color=None),
    AcceptCase(name="empty_color_is_unset", label=None, color="", expected_label=None, expected_color=None),
    AcceptCase(name="whitespace_color_is_unset", label=None, color="  ", expected_label=None, expected_color=None),
    AcceptCase(
        name="color_is_trimmed", label=None, color=" GRAY ", expected_label=None, expected_color=InstanceColor.GRAY
    ),
    AcceptCase(name="lowercase_color", label=None, color="red", expected_label=None, expected_color=InstanceColor.RED),
    AcceptCase(name="both_unset", label=None, color=None, expected_label=None, expected_color=None),
]


@pytest.mark.parametrize("case", ACCEPT_CASES, ids=lambda case: case.name)
def test_instance_settings_accepts_and_normalizes(case: AcceptCase) -> None:
    settings = InstanceSettings(label=case.label, color=case.color)

    assert (settings.label, settings.color) == (case.expected_label, case.expected_color)


@dataclass
class RejectCase:
    name: str
    label: str | None
    color: str | None
    expected_message: str


REJECT_CASES: list[RejectCase] = [
    RejectCase(
        name="label_too_long",
        label="a" * 33,
        color=None,
        expected_message="Value error, INFRAHUB_INSTANCE_LABEL cannot be longer than 32 characters",
    ),
    RejectCase(
        name="label_with_line_feed",
        label="a\nb",
        color=None,
        expected_message="Value error, INFRAHUB_INSTANCE_LABEL cannot contain control characters",
    ),
    RejectCase(
        name="label_with_bidi_override",
        label="a\u202eb",
        color=None,
        expected_message="Value error, INFRAHUB_INSTANCE_LABEL cannot contain control characters",
    ),
    RejectCase(
        name="unknown_color",
        label=None,
        color="PINK",
        expected_message="INFRAHUB_INSTANCE_COLOR must be one of RED, AMBER, GREEN, BLUE, INDIGO, PURPLE, GRAY",
    ),
]


@pytest.mark.parametrize("case", REJECT_CASES, ids=lambda case: case.name)
def test_instance_settings_rejects(case: RejectCase) -> None:
    with pytest.raises(ValidationError, match=re.escape(case.expected_message)):
        InstanceSettings(label=case.label, color=case.color)
