from typing import Any

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


def test_event_context_exposes_no_priority() -> None:
    event_context = build_context(priority=WorkflowPriority.HIGH).to_event_context()

    assert "priority" not in type(event_context).model_fields
    assert not hasattr(event_context, "priority")
    assert "priority" not in event_context.model_dump()


def test_request_context_exposes_no_priority() -> None:
    request_context = build_context(priority=WorkflowPriority.HIGH).to_request_context()

    assert "priority" not in type(request_context).model_fields
    assert not hasattr(request_context, "priority")
    assert "priority" not in request_context.model_dump()
