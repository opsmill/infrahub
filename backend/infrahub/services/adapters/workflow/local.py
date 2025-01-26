from __future__ import annotations

import uuid
from typing import Any, Optional

from typing_extensions import TYPE_CHECKING

from infrahub.workers.utils import inject_service_parameter
from infrahub.workflows.models import WorkflowDefinition, WorkflowInfo

from . import InfrahubWorkflow, Return

if TYPE_CHECKING:
    from infrahub.services import InfrahubServices


class WorkflowLocalExecution(InfrahubWorkflow):
    service: Optional[InfrahubServices] = None  # needed for local injections

    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        expected_return: type[Return] | None = None,  # noqa: ARG002
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,  # noqa: ARG002
    ) -> Any:
        if self.service is None:
            raise ValueError("WorkflowLocalExecution.service is not initialized")

        flow_func = workflow.load_function()
        parameters = dict(parameters) if parameters is not None else {}  # avoid mutating input parameters
        inject_service_parameter(func=flow_func, parameters=parameters, service=self.service)
        parameters = flow_func.validate_parameters(parameters=parameters)

        return await flow_func(**parameters)

    async def submit_workflow(
        self,
        workflow: WorkflowDefinition,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,  # noqa: ARG002
    ) -> WorkflowInfo:
        await self.execute_workflow(workflow=workflow, parameters=parameters)
        return WorkflowInfo(id=uuid.uuid4())
