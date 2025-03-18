import importlib
import inspect
from typing import Any, Awaitable, TypeVar
from uuid import UUID

from prefect import Flow
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.actions import DeploymentScheduleCreate
from prefect.client.schemas.objects import FlowRun
from prefect.client.schemas.schedules import CronSchedule
from pydantic import BaseModel, Field
from typing_extensions import Self

from infrahub import __version__

from .constants import TAG_NAMESPACE, WorkflowTag, WorkflowType

TASK_RESULT_STORAGE_NAME = "infrahub-storage"

WorkflowReturn = TypeVar("WorkflowReturn")


class WorkerPoolDefinition(BaseModel):
    name: str
    worker_type: str | None = None
    description: str = ""


class WorkflowInfo(BaseModel):
    id: UUID
    info: FlowRun | None = None

    @classmethod
    def from_flow(cls, flow_run: FlowRun) -> Self:
        return cls(id=flow_run.id, info=flow_run)


class WorkflowParameter(BaseModel):
    name: str
    type: str
    required: bool


class WorkflowDefinition(BaseModel):
    name: str
    type: WorkflowType = WorkflowType.INTERNAL
    module: str
    function: str
    cron: str | None = None
    tags: list[WorkflowTag] = Field(default_factory=list)

    @property
    def entrypoint(self) -> str:
        return f"backend/{self.module.replace('.', '/')}:{self.function}"

    @property
    def full_name(self) -> str:
        return f"{self.name}/{self.name}"

    def to_deployment(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"name": self.name, "entrypoint": self.entrypoint, "tags": self.get_tags()}
        if self.type == WorkflowType.CORE:
            payload["version"] = __version__
        if self.cron:
            payload["schedules"] = [DeploymentScheduleCreate(schedule=CronSchedule(cron=self.cron))]

        return payload

    def get_tags(self) -> list[str]:
        tags: list[str] = []
        if self.type != WorkflowType.INTERNAL:
            tags.append(TAG_NAMESPACE)
        tags.append(WorkflowTag.WORKFLOWTYPE.render(identifier=self.type.value))
        tags += [tag.render() for tag in self.tags]
        return tags

    async def save(self, client: PrefectClient, work_pool: WorkerPoolDefinition) -> UUID:
        flow_id = await client.create_flow_from_name(self.name)
        data = self.to_deployment()
        data["work_pool_name"] = work_pool.name
        return await client.create_deployment(flow_id=flow_id, **data)

    def load_function(self) -> Flow[Any, Awaitable]:
        module = importlib.import_module(self.module)
        return getattr(module, self.function)

    def get_parameters(self) -> dict[str, WorkflowParameter]:
        fn = self.load_function()
        signature = inspect.signature(fn.fn)
        required_params = fn.parameters.required

        ANNOTATIONS_TO_EXCLUDE = ["InfrahubServices"]

        params = {}
        for item in signature.parameters.values():
            # Workflow signature will return a string if 'from __future__ import annotations' is used
            # Otherwise it will return a type object
            annotation = item.annotation if isinstance(item.annotation, str) else item.annotation.__name__
            if annotation in ANNOTATIONS_TO_EXCLUDE:
                continue
            param = WorkflowParameter(name=item.name, type=annotation, required=item.name in required_params)
            params[item.name] = param

        return params
