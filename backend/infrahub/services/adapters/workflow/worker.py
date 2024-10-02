from __future__ import annotations

from typing import TYPE_CHECKING, Any, Awaitable, Callable

from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.deployments import run_deployment
from prefect.exceptions import ObjectAlreadyExists

from infrahub.workflows.catalogue import worker_pools, workflows

from . import InfrahubWorkflow, Return

if TYPE_CHECKING:
    from prefect.client.schemas.objects import FlowRun

    from infrahub.services import InfrahubServices
    from infrahub.workflows.models import WorkflowDefinition


class WorkflowWorkerExecution(InfrahubWorkflow):
    async def initialize(self, service: InfrahubServices) -> None:
        """Initialize the Workflow engine"""

        async with get_client(sync_client=False) as client:
            for worker in worker_pools:
                wp = WorkPoolCreate(
                    name=worker.name,
                    type=worker.worker_type,
                    description=worker.description,
                )
                try:
                    await client.create_work_pool(work_pool=wp)
                    service.log.info(f"work pool {worker} created successfully ... ")
                except ObjectAlreadyExists:
                    service.log.info(f"work pool {worker} already present ")

            # Create deployment
            for workflow in workflows:
                flow_id = await client.create_flow_from_name(workflow.name)
                await client.create_deployment(flow_id=flow_id, **workflow.to_deployment())

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
            return response.state.result(raise_on_failure=True)

        if function:
            return await function(**kwargs)

        raise ValueError("either a workflow definition or a flow must be provided")
