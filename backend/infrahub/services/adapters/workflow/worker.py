from typing import Any, Awaitable, Callable

from prefect.deployments import run_deployment

from infrahub.workflows.models import WorkflowDefinition

from . import InfrahubWorkflow, Return


class WorkflowWorkerExecution(InfrahubWorkflow):
    async def execute(
        self,
        workflow: WorkflowDefinition | None = None,
        function: Callable[..., Awaitable[Return]] | None = None,
        **kwargs: dict[str, Any],
    ) -> Return:
        if workflow:
            return await run_deployment(name=workflow.name, parameters=kwargs or {})  # type: ignore[return-value, misc]

        if function:
            return await function(**kwargs)

        raise ValueError("either a workflow definition or a flow must be provided")
