from __future__ import annotations

from typing import TYPE_CHECKING, Any, Awaitable, Callable, ParamSpec, TypeVar

if TYPE_CHECKING:
    from infrahub.services import InfrahubServices
    from infrahub.workflows.models import WorkflowDefinition

Return = TypeVar("Return")
Params = ParamSpec("Params")

FuncType = Callable[Params, Return]


class InfrahubWorkflow:
    async def initialize(self, service: InfrahubServices) -> None:
        """Initialize the Workflow engine"""

    async def execute(
        self,
        workflow: WorkflowDefinition | None = None,
        function: Callable[..., Awaitable[Return]] | None = None,
        **kwargs: Any,
    ) -> Return:
        raise NotImplementedError()
