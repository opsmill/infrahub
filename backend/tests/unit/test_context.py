from typing import Any

from infrahub_sdk.constants import Priority

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.workflows.constants import WorkflowPriority


def build_context(priority: WorkflowPriority | None = None) -> InfrahubContext:
    return InfrahubContext(
        branch=BranchContext(name="main", id="1111aaaa-0000-0000-0000-000000000000"),
        account=AccountSession(auth_type=AuthType.JWT, authenticated=True, account_id="account-a"),
        priority=priority,
    )


def build_payload() -> dict[str, Any]:
    return {
        "branch": {"name": "main", "id": "1111aaaa-0000-0000-0000-000000000000"},
        "account": {"auth_type": "jwt", "authenticated": True, "account_id": "account-a"},
    }


def test_priority_defaults_to_none() -> None:
    context = InfrahubContext(
        branch=BranchContext(name="main"),
        account=AccountSession(auth_type=AuthType.JWT, authenticated=True, account_id="account-a"),
    )

    assert context.priority is None


def test_payload_without_priority_deserializes_to_none() -> None:
    context = InfrahubContext.model_validate(build_payload())

    assert context.priority is None


def test_payload_with_priority_deserializes_to_enum() -> None:
    payload = build_payload()
    payload["priority"] = "high"

    context = InfrahubContext.model_validate(payload)

    assert context.priority is WorkflowPriority.HIGH


def test_payload_with_unknown_extra_key_still_deserializes() -> None:
    payload = build_payload()
    payload["some_future_field"] = "whatever"

    context = InfrahubContext.model_validate(payload)

    assert context.branch.name == "main"
    assert context.priority is None


def test_event_context_carries_priority() -> None:
    event_context = build_context(priority=WorkflowPriority.HIGH).to_event_context()

    assert event_context.priority is WorkflowPriority.HIGH


def test_event_context_priority_none_when_unset() -> None:
    event_context = build_context(priority=None).to_event_context()

    assert event_context.priority is None


def test_request_context_maps_medium_priority_to_normal() -> None:
    request_context = build_context(priority=WorkflowPriority.MEDIUM).to_request_context()

    assert request_context.priority is Priority.NORMAL


def test_request_context_priority_none_when_unset() -> None:
    request_context = build_context(priority=None).to_request_context()

    assert request_context.priority is None
