from typing import Any

from prefect import flow

from infrahub.events.models import EventBranchContext, EventContext
from infrahub.profiles.tasks import objects_profiles_refresh_multiple
from infrahub.services.adapters.workflow.priority import prepare_dispatch
from infrahub.workers.utils import inject_context_parameter
from infrahub.workflows.catalogue import PROFILE_REFRESH_MULTIPLE
from infrahub.workflows.constants import WorkflowPriority


@flow
async def flow_with_optional_context(name: str, context: EventContext | None = None) -> None: ...


def build_event_context() -> EventContext:
    return EventContext(branch=EventBranchContext(name="main"), account_id="account-a")


def test_inject_context_parameter_stamps_a_string_optional_annotation() -> None:
    """A flow module with postponed annotations declares the parameter as the string ``EventContext | None``."""
    context = build_event_context()
    parameters: dict[str, Any] = {"branch_name": "main", "node_ids": ["node-a"], "context": context}
    dispatch_context, _ = prepare_dispatch(workflow=PROFILE_REFRESH_MULTIPLE, context=context, priority=None)

    inject_context_parameter(func=objects_profiles_refresh_multiple, parameters=parameters, context=dispatch_context)

    assert parameters == {
        "branch_name": "main",
        "node_ids": ["node-a"],
        "context": context.model_copy(update={"priority": WorkflowPriority.LOW}),
    }


def test_inject_context_parameter_fills_an_evaluated_optional_annotation() -> None:
    context = build_event_context()
    parameters: dict[str, Any] = {"name": "repo-a"}

    inject_context_parameter(func=flow_with_optional_context, parameters=parameters, context=context)

    assert parameters == {"name": "repo-a", "context": context}
