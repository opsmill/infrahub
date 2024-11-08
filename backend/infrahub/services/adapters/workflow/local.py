import uuid
from typing import Any

from infrahub.workflows.models import WorkflowDefinition, WorkflowInfo

from . import InfrahubWorkflow, Return


class WorkflowLocalExecution(InfrahubWorkflow):
    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        expected_return: type[Return] | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Any:
        fn = workflow.get_function()
        return await fn(**parameters or {})

    async def submit_workflow(
        self,
        workflow: WorkflowDefinition,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> WorkflowInfo:
        await self.execute_workflow(workflow=workflow, parameters=parameters)
        return WorkflowInfo(id=uuid.uuid4())
