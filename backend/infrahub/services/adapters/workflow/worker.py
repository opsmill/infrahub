from __future__ import annotations

from typing import TYPE_CHECKING, Any, overload

from prefect.client.orchestration import get_client
from prefect.client.schemas.objects import StateType
from prefect.context import AsyncClientContext
from prefect.deployments import run_deployment
from prefect.exceptions import ObjectNotFound

from infrahub import config, lock
from infrahub.log import get_logger
from infrahub.workers.utils import inject_context_parameter
from infrahub.workflows.catalogue import INFRAHUB_WORKER_POOL
from infrahub.workflows.initialization import setup_task_manager, setup_task_manager_identifiers
from infrahub.workflows.models import WorkflowInfo

from . import InfrahubWorkflow, Return

if TYPE_CHECKING:
    from prefect.client.schemas.objects import FlowRun

    from infrahub.context import InfrahubContext
    from infrahub.events.models import EventContext
    from infrahub.tls.registry import TlsContextRegistry
    from infrahub.workflows.constants import WorkflowPriority
    from infrahub.workflows.models import WorkflowDefinition

log = get_logger()


class WorkflowWorkerExecution(InfrahubWorkflow):
    def __init__(self, tls_registry: TlsContextRegistry) -> None:
        self._tls_registry = tls_registry

    @staticmethod
    async def initialize(component_is_primary_server: bool, is_initial_setup: bool = False) -> None:
        if is_initial_setup:
            await WorkflowWorkerExecution._setup_task_manager()
            await setup_task_manager_identifiers()
        elif component_is_primary_server:
            await WorkflowWorkerExecution._setup_task_manager()

    @staticmethod
    async def _setup_task_manager() -> None:
        async with lock.registry.get(name="global.worker.taskmgr.init"):
            await setup_task_manager()

    @staticmethod
    async def _resolve_work_queue_name(workflow: WorkflowDefinition, priority: WorkflowPriority) -> str | None:
        """Return the queue name for the requested priority, or None when the queue is missing.

        A missing queue is logged and the dispatch falls back to the deployment's own queue,
        so queue-layout drift can never make a dispatch fail.
        """
        async with get_client(sync_client=False) as client:
            try:
                await client.read_work_queue_by_name(name=priority.queue_name, work_pool_name=INFRAHUB_WORKER_POOL.name)
            except ObjectNotFound:
                log.warning(
                    f"Work queue '{priority.queue_name}' not found in work pool '{INFRAHUB_WORKER_POOL.name}', "
                    f"dispatching workflow '{workflow.name}' to its deployment's own queue instead"
                )
                return None
        return priority.queue_name

    @overload
    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        expected_return: type[Return],
        context: InfrahubContext | EventContext | None = None,
        parameters: dict[str, Any] | None = ...,
        tags: list[str] | None = ...,
        priority: WorkflowPriority | None = ...,
    ) -> Return: ...

    @overload
    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        expected_return: None = ...,
        context: InfrahubContext | EventContext | None = ...,
        parameters: dict[str, Any] | None = ...,
        tags: list[str] | None = ...,
        priority: WorkflowPriority | None = ...,
    ) -> Any: ...

    # TODO Make expected_return mandatory and remove above overloads.
    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        expected_return: type[Return] | None = None,  # noqa: ARG002
        context: InfrahubContext | EventContext | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        priority: WorkflowPriority | None = None,
    ) -> Any:
        flow_func = workflow.load_function()
        parameters = dict(parameters) if parameters is not None else {}
        inject_context_parameter(func=flow_func, parameters=parameters, context=context)

        work_queue_name: str | None = None
        if priority is not None:
            work_queue_name = await self._resolve_work_queue_name(workflow=workflow, priority=priority)

        response: FlowRun = await run_deployment(
            name=workflow.full_name,
            poll_interval=1,
            parameters=parameters or {},
            tags=tags,
            work_queue_name=work_queue_name,
        )  # type: ignore[misc]
        if not response.state:
            raise RuntimeError("Unable to read state from the response")

        if response.state.type == StateType.CRASHED:
            raise RuntimeError(response.state.message)

        return await response.state.result(raise_on_failure=True)

    async def submit_workflow(
        self,
        workflow: WorkflowDefinition,
        context: InfrahubContext | EventContext | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        priority: WorkflowPriority | None = None,
    ) -> WorkflowInfo:
        flow_func = workflow.load_function()
        parameters = dict(parameters) if parameters is not None else {}
        inject_context_parameter(func=flow_func, parameters=parameters, context=context)

        work_queue_name: str | None = None
        if priority is not None:
            work_queue_name = await self._resolve_work_queue_name(workflow=workflow, priority=priority)

        tls_insecure = config.SETTINGS.http.tls_insecure
        tls_ca_bundle = config.SETTINGS.http.tls_ca_bundle
        tls_context = self._tls_registry.get(insecure=tls_insecure, ca_bundle=tls_ca_bundle)
        async with AsyncClientContext(httpx_settings={"verify": tls_context}):
            flow_run = await run_deployment(
                name=workflow.full_name,
                timeout=0,
                parameters=parameters or {},
                tags=tags,
                work_queue_name=work_queue_name,
            )  # type: ignore[misc]
        return WorkflowInfo.from_flow(flow_run=flow_run)
