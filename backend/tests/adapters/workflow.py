from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from infrahub.core.constants import ValidatorConclusion
from infrahub.services.adapters.workflow import InfrahubWorkflow
from infrahub.workflows.models import WorkflowDefinition, WorkflowInfo

if TYPE_CHECKING:
    from infrahub.context import InfrahubContext
    from infrahub.events.models import EventContext


class WorkflowRecorder(InfrahubWorkflow):
    """Records workflow calls without executing them. Use for testing code that submits workflows."""

    def __init__(self) -> None:
        self.execute_calls: list[dict[str, Any]] = []
        self.submit_calls: list[dict[str, Any]] = []

    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        expected_return: type | None = None,
        context: InfrahubContext | EventContext | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Any:
        self.execute_calls.append({"workflow": workflow, "parameters": parameters or {}})
        if expected_return is ValidatorConclusion:
            return ValidatorConclusion.SUCCESS
        return None

    async def submit_workflow(
        self,
        workflow: WorkflowDefinition,
        context: InfrahubContext | EventContext | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> WorkflowInfo:
        self.submit_calls.append({"workflow": workflow, "parameters": parameters or {}})
        return WorkflowInfo(id=uuid.uuid4())

    def get_execute_calls_for(self, workflow: WorkflowDefinition) -> list[dict[str, Any]]:
        return [c for c in self.execute_calls if c["workflow"] == workflow]

    def get_submit_calls_for(self, workflow: WorkflowDefinition) -> list[dict[str, Any]]:
        return [c for c in self.submit_calls if c["workflow"] == workflow]
