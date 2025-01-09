from __future__ import annotations

import inspect
import uuid
from typing import Any, Optional

from typing_extensions import TYPE_CHECKING

from infrahub.workers.utils import inject_service_parameter, load_flow_function
from infrahub.workflows.models import WorkflowDefinition, WorkflowInfo

from . import InfrahubWorkflow, Return

if TYPE_CHECKING:
    from ... import InfrahubServices


class WorkflowLocalExecution(InfrahubWorkflow):
    service: Optional[InfrahubServices] = None

    async def initialize(self, service: InfrahubServices) -> None:
        self.service = service

    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        expected_return: type[Return] | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Any:
        assert self.service is not None, "service not initialized"

        flow_func = load_flow_function(module_path=workflow.module, flow_name=workflow.function)
        if parameters is not None:
            params = dict(parameters)  # avoid mutating input parameters
            sig = inspect.signature(flow_func)
            if "service" in sig.parameters:
                inject_service_parameter(service=self.service, parameters=params)
            params = flow_func.validate_parameters(parameters=params)
        else:
            params = {}

        return await flow_func(**params)

    async def submit_workflow(
        self,
        workflow: WorkflowDefinition,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> WorkflowInfo:
        await self.execute_workflow(workflow=workflow, parameters=parameters)
        return WorkflowInfo(id=uuid.uuid4())
