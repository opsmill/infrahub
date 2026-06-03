from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable, ParamSpec, TypeVar, overload

if TYPE_CHECKING:
    from infrahub.context import InfrahubContext
    from infrahub.workflows.models import WorkflowDefinition, WorkflowInfo

Return = TypeVar("Return")
Params = ParamSpec("Params")

FuncType = Callable[Params, Return]


class InfrahubWorkflow(ABC):
    @overload
    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        expected_return: type[Return],
        context: InfrahubContext | None = ...,
        parameters: dict[str, Any] | None = ...,
        tags: list[str] | None = ...,
        timeout: float | None = ...,  # noqa: ASYNC109
    ) -> Return: ...

    @overload
    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        expected_return: None = ...,
        context: InfrahubContext | None = ...,
        parameters: dict[str, Any] | None = ...,
        tags: list[str] | None = ...,
        timeout: float | None = ...,  # noqa: ASYNC109
    ) -> Any: ...

    @abstractmethod
    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        expected_return: type[Return] | None = None,
        context: InfrahubContext | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        timeout: float | None = None,  # noqa: ASYNC109
    ) -> Any:
        raise NotImplementedError()

    @abstractmethod
    async def submit_workflow(
        self,
        workflow: WorkflowDefinition,
        context: InfrahubContext | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> WorkflowInfo:
        raise NotImplementedError()
