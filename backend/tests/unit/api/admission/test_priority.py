from dataclasses import dataclass

import pytest

from infrahub.api.admission.priority import Priority, parse_priority


@dataclass
class ParseCase:
    name: str
    header_value: str | None
    expected_priority: Priority
    expected_explicit: bool


PARSE_CASES = [
    ParseCase(name="high", header_value="high", expected_priority=Priority.HIGH, expected_explicit=True),
    ParseCase(name="medium", header_value="medium", expected_priority=Priority.MEDIUM, expected_explicit=True),
    ParseCase(name="low", header_value="low", expected_priority=Priority.LOW, expected_explicit=True),
    ParseCase(name="mixed-case-high", header_value="HIGH", expected_priority=Priority.HIGH, expected_explicit=True),
    ParseCase(name="mixed-case-low", header_value="Low", expected_priority=Priority.LOW, expected_explicit=True),
    ParseCase(
        name="surrounding-whitespace",
        header_value="  high  ",
        expected_priority=Priority.HIGH,
        expected_explicit=True,
    ),
    ParseCase(name="empty", header_value="", expected_priority=Priority.MEDIUM, expected_explicit=False),
    ParseCase(name="whitespace-only", header_value="   ", expected_priority=Priority.MEDIUM, expected_explicit=False),
    ParseCase(name="none", header_value=None, expected_priority=Priority.MEDIUM, expected_explicit=False),
    ParseCase(name="invalid-urgent", header_value="urgent", expected_priority=Priority.MEDIUM, expected_explicit=False),
    ParseCase(name="invalid-garbage", header_value="!@#$", expected_priority=Priority.MEDIUM, expected_explicit=False),
]


@pytest.mark.parametrize("case", PARSE_CASES, ids=[c.name for c in PARSE_CASES])
def test_parse_priority(case: ParseCase) -> None:
    result = parse_priority(header_value=case.header_value)
    assert result.priority is case.expected_priority
    assert result.was_explicit is case.expected_explicit


def test_priority_ordering() -> None:
    assert Priority.HIGH < Priority.MEDIUM < Priority.LOW


def test_priority_labels() -> None:
    assert Priority.HIGH.label == "high"
    assert Priority.MEDIUM.label == "medium"
    assert Priority.LOW.label == "low"
