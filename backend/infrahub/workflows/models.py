import importlib
from typing import Any, Awaitable, Callable

from pydantic import BaseModel


class WorkflowDefinition(BaseModel):
    name: str
    work_pool_name: str
    module: str
    function: str
    # return_type: type

    @property
    def entrypoint(self) -> str:
        return f'backend/{self.module.replace(".", "/")}::{self.function}'

    def to_deployment(self) -> dict:
        return {"name": self.name, "work_pool_name": self.work_pool_name, "entrypoint": self.entrypoint}

    def get_function(self) -> Callable[..., Awaitable[Any]]:
        module = importlib.import_module(self.module)
        return getattr(module, self.function)

    def validate_workflow(self) -> None:
        self.get_function()
