from typing import Any, Awaitable, Callable, ParamSpec, TypeVar

from infrahub.workflows.models import WorkflowDefinition

Return = TypeVar("Return")
Params = ParamSpec("Params")

FuncType = Callable[Params, Return]


class InfrahubWorkflow:
    async def execute(
        self,
        workflow: WorkflowDefinition | None = None,
        function: Callable[..., Awaitable[Return]] | None = None,
        **kwargs: dict[str, Any],
    ) -> Any:
        raise NotImplementedError()
