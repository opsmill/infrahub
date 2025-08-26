from __future__ import annotations

import uuid
from typing import Any

from typing_extensions import TYPE_CHECKING

from infrahub.workers.utils import inject_context_parameter
from infrahub.workflows.models import WorkflowDefinition, WorkflowInfo

from . import InfrahubWorkflow, Return

if TYPE_CHECKING:
    from infrahub.context import InfrahubContext


class WorkflowLocalExecution(InfrahubWorkflow):
    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        expected_return: type[Return] | None = None,  # noqa: ARG002
        context: InfrahubContext | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,  # noqa: ARG002
    ) -> Any:
        flow_func = workflow.load_function()
        parameters = dict(parameters) if parameters is not None else {}  # avoid mutating input parameters
        inject_context_parameter(func=flow_func, parameters=parameters, context=context)

        parameters = flow_func.validate_parameters(parameters=parameters)
        return await flow_func(**parameters)

    async def submit_workflow(
        self,
        workflow: WorkflowDefinition,
        context: InfrahubContext | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,  # noqa: ARG002
    ) -> WorkflowInfo:
        await self.execute_workflow(workflow=workflow, context=context, parameters=parameters)
        return WorkflowInfo(id=uuid.uuid4())
