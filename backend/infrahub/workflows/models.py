import importlib
from typing import Any, Awaitable, Callable, Optional
from uuid import UUID

from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.actions import DeploymentScheduleCreate
from prefect.client.schemas.schedules import CronSchedule
from pydantic import BaseModel

from infrahub import __version__

from .constants import WorkflowType

TASK_RESULT_STORAGE_NAME = "infrahub-storage"


class WorkerPoolDefinition(BaseModel):
    name: str
    worker_type: str
    description: str = ""


class WorkflowDefinition(BaseModel):
    name: str
    type: WorkflowType = WorkflowType.INTERNAL
    module: str
    function: str
    cron: Optional[str] = None

    @property
    def entrypoint(self) -> str:
        return f'backend/{self.module.replace(".", "/")}:{self.function}'

    @property
    def full_name(self) -> str:
        return f"{self.name}/{self.name}"

    def to_deployment(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "entrypoint": self.entrypoint,
        }
        if self.type == WorkflowType.INTERNAL:
            payload["version"] = __version__
        if self.cron:
            payload["schedules"] = [DeploymentScheduleCreate(schedule=CronSchedule(cron=self.cron))]
        return payload

    async def save(self, client: PrefectClient, work_pool: WorkerPoolDefinition) -> UUID:
        flow_id = await client.create_flow_from_name(self.name)
        data = self.to_deployment()
        data["work_pool_name"] = work_pool.name
        return await client.create_deployment(flow_id=flow_id, **data)

    def get_function(self) -> Callable[..., Awaitable[Any]]:
        module = importlib.import_module(self.module)
        return getattr(module, self.function)

    def validate_workflow(self) -> None:
        self.get_function()
