from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise

import pytest

from infrahub.workflows.constants import WorkflowPriority


@dataclass
class PriorityTestCase:
    name: str
    priority: WorkflowPriority
    expected_value: str
    expected_queue_priority: int


PRIORITY_TEST_CASES = [
    PriorityTestCase(
        name="high",
        priority=WorkflowPriority.HIGH,
        expected_value="high",
        expected_queue_priority=1,
    ),
    PriorityTestCase(
        name="medium",
        priority=WorkflowPriority.MEDIUM,
        expected_value="medium",
        expected_queue_priority=2,
    ),
    PriorityTestCase(
        name="low",
        priority=WorkflowPriority.LOW,
        expected_value="low",
        expected_queue_priority=3,
    ),
]


def test_workflow_priority_members() -> None:
    assert [member.value for member in WorkflowPriority] == ["high", "medium", "low"]


@pytest.mark.parametrize("test_case", [pytest.param(test_case, id=test_case.name) for test_case in PRIORITY_TEST_CASES])
def test_workflow_priority_mapping(test_case: PriorityTestCase) -> None:
    assert test_case.priority.value == test_case.expected_value
    assert test_case.priority.queue_name == test_case.expected_value
    assert test_case.priority.queue_priority == test_case.expected_queue_priority


def test_queue_name_matches_value_for_every_member() -> None:
    for member in WorkflowPriority:
        assert member.queue_name == member.value


def test_queue_priorities_unique_and_strictly_increasing() -> None:
    queue_priorities = [member.queue_priority for member in WorkflowPriority]
    assert len(set(queue_priorities)) == len(queue_priorities)
    assert all(previous < current for previous, current in pairwise(queue_priorities))
