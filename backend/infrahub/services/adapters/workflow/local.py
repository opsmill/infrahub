from __future__ import annotations

import uuid
from typing import Any

from typing_extensions import TYPE_CHECKING

from infrahub.workers.utils import inject_context_parameter
from infrahub.workflows.models import WorkflowDefinition, WorkflowInfo

from . import InfrahubWorkflow, Return, prepare_dispatch

if TYPE_CHECKING:
    from infrahub.context import InfrahubContext
    from infrahub.events.models import EventContext
    from infrahub.workflows.constants import WorkflowPriority


class WorkflowLocalExecution(InfrahubWorkflow):
    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        expected_return: type[Return] | None = None,  # noqa: ARG002
        context: InfrahubContext | EventContext | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,  # noqa: ARG002
        priority: WorkflowPriority | None = None,
    ) -> Any:
        flow_func = workflow.load_function()
        parameters = dict(parameters) if parameters is not None else {}  # avoid mutating input parameters
        # Stamp the resolved priority into the dispatched context; local execution has no queues to route to.
        dispatch_context, _ = prepare_dispatch(workflow=workflow, context=context, priority=priority)
        inject_context_parameter(func=flow_func, parameters=parameters, context=dispatch_context)

        parameters = flow_func.validate_parameters(parameters=parameters)
        return await flow_func(**parameters)

    async def submit_workflow(
        self,
        workflow: WorkflowDefinition,
        context: InfrahubContext | EventContext | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,  # noqa: ARG002
        priority: WorkflowPriority | None = None,
    ) -> WorkflowInfo:
        await self.execute_workflow(workflow=workflow, context=context, parameters=parameters, priority=priority)
        return WorkflowInfo(id=uuid.uuid4())
