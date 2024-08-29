import importlib
from typing import Any, Awaitable, Callable, Optional

from prefect.client.schemas.actions import DeploymentScheduleCreate
from prefect.client.schemas.schedules import CronSchedule
from pydantic import BaseModel


class WorkerPoolDefinition(BaseModel):
    name: str
    worker_type: str
    description: str = ""


class WorkflowDefinition(BaseModel):
    name: str
    work_pool: WorkerPoolDefinition
    module: str
    function: str
    cron: Optional[str] = None

    @property
    def entrypoint(self) -> str:
        return f'backend/{self.module.replace(".", "/")}::{self.function}'

    def to_deployment(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "work_pool_name": self.work_pool.name,
            "entrypoint": self.entrypoint,
        }
        if self.cron:
            payload["schedules"] = [DeploymentScheduleCreate(schedule=CronSchedule(cron=self.cron))]
        return payload

    def get_function(self) -> Callable[..., Awaitable[Any]]:
        module = importlib.import_module(self.module)
        return getattr(module, self.function)

    def validate_workflow(self) -> None:
        self.get_function()
