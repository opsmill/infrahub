from dataclasses import dataclass

import pytest
from infrahub_sdk.constants import Priority

from infrahub.events.models import EventBranchContext, EventContext, workflow_priority_to_request_priority
from infrahub.workflows.constants import WorkflowPriority


@dataclass
class MappingCase:
    name: str
    workflow_priority: WorkflowPriority | None
    expected: Priority | None


MAPPING_CASES = [
    MappingCase(name="high", workflow_priority=WorkflowPriority.HIGH, expected=Priority.HIGH),
    MappingCase(name="medium-maps-to-normal", workflow_priority=WorkflowPriority.MEDIUM, expected=Priority.NORMAL),
    MappingCase(name="low", workflow_priority=WorkflowPriority.LOW, expected=Priority.LOW),
    MappingCase(name="none", workflow_priority=None, expected=None),
]


@pytest.mark.parametrize("case", [pytest.param(tc, id=tc.name) for tc in MAPPING_CASES])
def test_workflow_priority_to_request_priority(case: MappingCase) -> None:
    assert workflow_priority_to_request_priority(case.workflow_priority) == case.expected


def test_event_context_priority_survives_serialization_round_trip() -> None:
    event_context = EventContext(
        branch=EventBranchContext(name="main"), account_id="account-a", priority=WorkflowPriority.LOW
    )

    restored = EventContext.model_validate(event_context.to_event())

    assert restored.priority is WorkflowPriority.LOW


def test_event_context_payload_without_priority_deserializes_to_none() -> None:
    payload = {"branch": {"name": "main"}, "account_id": "account-a"}

    restored = EventContext.model_validate(payload)

    assert restored.priority is None


def test_event_context_to_request_context_maps_priority() -> None:
    event_context = EventContext(
        branch=EventBranchContext(name="main"), account_id="account-a", priority=WorkflowPriority.MEDIUM
    )

    request_context = event_context.to_request_context()

    assert request_context.account is not None
    assert request_context.account.id == "account-a"
    assert request_context.priority is Priority.NORMAL
