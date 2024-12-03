from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, ParamSpec, TypeVar, overload

if TYPE_CHECKING:
    from infrahub.services import InfrahubServices
    from infrahub.workflows.models import WorkflowDefinition, WorkflowInfo

Return = TypeVar("Return")
Params = ParamSpec("Params")

FuncType = Callable[Params, Return]


class InfrahubWorkflow:
    async def initialize(self, service: InfrahubServices) -> None:
        """Initialize the Workflow engine"""

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
        raise NotImplementedError("InfrahubWorkflow.execute_workflow is an abstract method")

    async def submit_workflow(
        self,
        workflow: WorkflowDefinition,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> WorkflowInfo:
        raise NotImplementedError("InfrahubWorkflow.submit_workflow is an abstract method")
