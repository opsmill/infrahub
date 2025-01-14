from __future__ import annotations

import uuid
from typing import Any, Optional

from typing_extensions import TYPE_CHECKING

from infrahub.workflows.models import WorkflowDefinition, WorkflowInfo

from . import InfrahubWorkflow, Return

if TYPE_CHECKING:
    from ... import InfrahubServices


class WorkflowLocalExecution(InfrahubWorkflow):
    service: Optional[InfrahubServices] = None  # needed for local injections

    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        expected_return: type[Return] | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Any:
        assert self.service is not None, "service not initialized"

        fn = workflow.load_function()
        return await fn(**parameters or {})

    async def submit_workflow(
        self,
        workflow: WorkflowDefinition,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> WorkflowInfo:
        await self.execute_workflow(workflow=workflow, parameters=parameters)
        return WorkflowInfo(id=uuid.uuid4())
