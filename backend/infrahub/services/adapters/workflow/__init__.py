from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable, ParamSpec, TypeVar, overload

if TYPE_CHECKING:
    from infrahub.services import InfrahubServices
    from infrahub.workflows.models import WorkflowDefinition, WorkflowInfo

Return = TypeVar("Return")
Params = ParamSpec("Params")

FuncType = Callable[Params, Return]


class InfrahubWorkflow(ABC):
    @abstractmethod
    async def initialize(self, service: InfrahubServices) -> None:
        raise NotImplementedError()

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

    @abstractmethod
    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        expected_return: type[Return] | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Any:
        raise NotImplementedError()

    @abstractmethod
    async def submit_workflow(
        self,
        workflow: WorkflowDefinition,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> WorkflowInfo:
        raise NotImplementedError()
