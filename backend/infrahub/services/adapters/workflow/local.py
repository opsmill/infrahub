from typing import Any, Awaitable, Callable

from infrahub.workflows.models import WorkflowDefinition

from . import InfrahubWorkflow, Return


class WorkflowLocalExecution(InfrahubWorkflow):
    async def execute(
        self,
        workflow: WorkflowDefinition | None = None,
        function: Callable[..., Awaitable[Return]] | None = None,
        **kwargs: dict[str, Any],
    ) -> Return:
        if workflow:
            fn = workflow.get_function()
            return await fn(**kwargs)
        if function:
            return await function(**kwargs)
        raise ValueError("either a workflow definition or a flow must be provided")
