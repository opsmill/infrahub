from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from infrahub.core.constants import ValidatorConclusion
from infrahub.services.adapters.workflow import InfrahubWorkflow
from infrahub.workflows.models import WorkflowDefinition, WorkflowInfo

if TYPE_CHECKING:
    from infrahub.context import InfrahubContext
    from infrahub.events.models import EventContext
    from infrahub.workflows.constants import WorkflowPriority


class WorkflowRecorder(InfrahubWorkflow):
    """Records workflow calls without executing them. Use for testing code that submits workflows."""

    def __init__(self) -> None:
<<<<<<< HEAD
        self.calls: list[dict[str, Any]] = []

    def reset(self) -> None:
        # execute_calls/submit_calls are derived views, so clearing them leaves the backing store
        # untouched; reset the store itself to isolate one test's recorded calls from the next.
        self.calls.clear()

    @property
    def execute_calls(self) -> list[dict[str, Any]]:
        return [call for call in self.calls if call["kind"] == "execute"]

    @property
    def submit_calls(self) -> list[dict[str, Any]]:
        return [call for call in self.calls if call["kind"] == "submit"]
=======
        self.execute_calls: list[dict[str, Any]] = []
        self.submit_calls: list[dict[str, Any]] = []
        self.execute_results: dict[str, Any] = {}
>>>>>>> stable

    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        expected_return: type | None = None,
        context: InfrahubContext | EventContext | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        priority: WorkflowPriority | None = None,
    ) -> Any:
<<<<<<< HEAD
        self.calls.append({"kind": "execute", "workflow": workflow, "parameters": parameters or {}})
=======
        self.execute_calls.append({"workflow": workflow, "parameters": parameters or {}})
        if workflow.name in self.execute_results:
            return self.execute_results[workflow.name]
>>>>>>> stable
        if expected_return is ValidatorConclusion:
            return ValidatorConclusion.SUCCESS
        return None

    async def submit_workflow(
        self,
        workflow: WorkflowDefinition,
        context: InfrahubContext | EventContext | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        priority: WorkflowPriority | None = None,
    ) -> WorkflowInfo:
        self.calls.append({"kind": "submit", "workflow": workflow, "parameters": parameters or {}, "tags": tags or []})
        return WorkflowInfo(id=uuid.uuid4())

    def get_execute_calls_for(self, workflow: WorkflowDefinition) -> list[dict[str, Any]]:
        return [call for call in self.execute_calls if call["workflow"] == workflow]

    def get_submit_calls_for(self, workflow: WorkflowDefinition) -> list[dict[str, Any]]:
        return [call for call in self.submit_calls if call["workflow"] == workflow]
