from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from infrahub.core.constants import ValidatorConclusion
from infrahub.services.adapters.workflow import InfrahubWorkflow
from infrahub.workflows.models import WorkflowDefinition, WorkflowInfo

if TYPE_CHECKING:
    from infrahub.context import InfrahubContext


class WorkflowRecorder(InfrahubWorkflow):
    """Records workflow calls without executing them. Use for testing code that submits workflows."""

    def __init__(self) -> None:
        self.execute_calls: list[dict[str, Any]] = []
        self.submit_calls: list[dict[str, Any]] = []
        self.all_calls: list[dict[str, Any]] = []

    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        expected_return: type | None = None,
        context: InfrahubContext | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Any:
        record = {"workflow": workflow, "parameters": parameters or {}, "type": "execute"}
        self.execute_calls.append(record)
        self.all_calls.append(record)
        if expected_return is ValidatorConclusion:
            return ValidatorConclusion.SUCCESS
        return None

    async def submit_workflow(
        self,
        workflow: WorkflowDefinition,
        context: InfrahubContext | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> WorkflowInfo:
        record = {"workflow": workflow, "parameters": parameters or {}, "type": "submit"}
        self.submit_calls.append(record)
        self.all_calls.append(record)
        return WorkflowInfo(id=uuid.uuid4())

    def get_execute_calls_for(self, workflow: WorkflowDefinition) -> list[dict[str, Any]]:
        return [c for c in self.execute_calls if c["workflow"] == workflow]

    def get_submit_calls_for(self, workflow: WorkflowDefinition) -> list[dict[str, Any]]:
        return [c for c in self.submit_calls if c["workflow"] == workflow]
