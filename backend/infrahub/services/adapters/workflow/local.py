from __future__ import annotations

import uuid
from typing import Any

from typing_extensions import TYPE_CHECKING

from infrahub.workers.utils import inject_context_parameter, inject_service_parameter
from infrahub.workflows.models import WorkflowDefinition, WorkflowInfo

from . import InfrahubWorkflow, Return

if TYPE_CHECKING:
    from infrahub.context import InfrahubContext
    from infrahub.services import InfrahubServices


class WorkflowLocalExecution(InfrahubWorkflow):
    service: InfrahubServices | None = None  # needed for local injections

    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        expected_return: type[Return] | None = None,  # noqa: ARG002
        context: InfrahubContext | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,  # noqa: ARG002
    ) -> Any:
        if self.service is None:
            raise ValueError("WorkflowLocalExecution.service is not initialized")

        flow_func = workflow.load_function()
        parameters = dict(parameters) if parameters is not None else {}  # avoid mutating input parameters
        inject_service_parameter(func=flow_func, parameters=parameters, service=self.service)
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
