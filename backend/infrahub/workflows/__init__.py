from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, ParamSpec, TypeVar

from prefect.deployments import run_deployment

from .models import WorkflowDefinition

Return = TypeVar("Return")
Params = ParamSpec("Params")

FuncType = Callable[Params, Return]


class WorkflowExecutionDriver(ABC):
    @abstractmethod
    async def execute(
        self,
        workflow: WorkflowDefinition | None = None,
        function: Callable[..., Awaitable[Return]] | None = None,
        **kwargs: dict[str, Any],
    ) -> Any: ...


class WorkflowWorkerExecution(WorkflowExecutionDriver):
    async def execute(
        self,
        workflow: WorkflowDefinition | None = None,
        function: Callable[..., Awaitable[Return]] | None = None,
        **kwargs: dict[str, Any],
    ) -> Return:
        if workflow:
            return run_deployment(name=workflow.name, parameters=kwargs or {})  # type: ignore[return-value]

        if function:
            return await function(**kwargs)

        raise ValueError("either a workflow definition or a flow must be provided")


class WorkflowLocalExecution(WorkflowExecutionDriver):
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


driver: WorkflowExecutionDriver = WorkflowLocalExecution()
