from __future__ import annotations

from typing import TYPE_CHECKING, Any, Awaitable, Callable

from prefect.client.schemas import StateType
from prefect.deployments import run_deployment

from infrahub.workflows.initialization import setup_task_manager

from . import InfrahubWorkflow, Return

if TYPE_CHECKING:
    from prefect.client.schemas.objects import FlowRun

    from infrahub.services import InfrahubServices
    from infrahub.workflows.models import WorkflowDefinition


class WorkflowWorkerExecution(InfrahubWorkflow):
    async def initialize(self, service: InfrahubServices) -> None:
        """Initialize the Workflow engine"""

        if await service.component.is_primary_api():
            await setup_task_manager()

    async def execute(
        self,
        workflow: WorkflowDefinition | None = None,
        function: Callable[..., Awaitable[Return]] | None = None,
        **kwargs: Any,
    ) -> Return:
        if workflow:
            response: FlowRun = await run_deployment(name=workflow.full_name, parameters=kwargs or {})  # type: ignore[return-value, misc]
            if not response.state:
                raise RuntimeError("Unable to read state from the response")

            if response.state.type == StateType.CRASHED:
                raise RuntimeError(response.state.message)

            return await response.state.result(raise_on_failure=True, fetch=True)  # type: ignore[call-overload]

        if function:
            return await function(**kwargs)

        raise ValueError("either a workflow definition or a flow must be provided")
