from __future__ import annotations

from typing import TYPE_CHECKING, Any, overload

from prefect.client.schemas.objects import StateType
from prefect.deployments import run_deployment

from infrahub.workflows.initialization import setup_task_manager
from infrahub.workflows.models import WorkflowInfo

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

    @overload
    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        expected_return: type[Return],
        parameters: dict[str, Any] | None = ...,
        tags: list[str] | None = ...,
    ) -> Return: ...

    @overload
    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        expected_return: None = ...,
        parameters: dict[str, Any] | None = ...,
        tags: list[str] | None = ...,
    ) -> Any: ...

    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        expected_return: type[Return] | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Any:
        response: FlowRun = await run_deployment(
            name=workflow.full_name, poll_interval=1, parameters=parameters or {}, tags=tags
        )  # type: ignore[return-value, misc]
        if not response.state:
            raise RuntimeError("Unable to read state from the response")

        if response.state.type == StateType.CRASHED:
            raise RuntimeError(response.state.message)

        return await response.state.result(raise_on_failure=True, fetch=True)  # type: ignore[call-overload]

    async def submit_workflow(
        self, workflow: WorkflowDefinition, parameters: dict[str, Any] | None = None, tags: list[str] | None = None
    ) -> WorkflowInfo:
        flow_run = await run_deployment(name=workflow.full_name, timeout=0, parameters=parameters or {}, tags=tags)  # type: ignore[return-value, misc]
        return WorkflowInfo.from_flow(flow_run=flow_run)
