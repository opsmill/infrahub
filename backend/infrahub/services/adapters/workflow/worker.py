from __future__ import annotations

from typing import TYPE_CHECKING, Any, overload

from prefect.client.schemas.objects import StateType
from prefect.context import AsyncClientContext
from prefect.deployments import run_deployment
from prefect.flow_runs import wait_for_flow_run

from infrahub import config, lock
from infrahub.exceptions import ServiceUnavailableError
from infrahub.workers.utils import inject_context_parameter
from infrahub.workflows.initialization import setup_task_manager, setup_task_manager_identifiers
from infrahub.workflows.models import WorkflowInfo

from . import InfrahubWorkflow, Return

if TYPE_CHECKING:
    from prefect.client.schemas.objects import FlowRun

    from infrahub.context import InfrahubContext
    from infrahub.tls.registry import TlsContextRegistry
    from infrahub.workflows.models import WorkflowDefinition


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

    @overload
    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        expected_return: type[Return],
        context: InfrahubContext | None = None,
        parameters: dict[str, Any] | None = ...,
        tags: list[str] | None = ...,
        timeout_seconds: float | None = ...,
    ) -> Return: ...

    @overload
    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        expected_return: None = ...,
        context: InfrahubContext | None = ...,
        parameters: dict[str, Any] | None = ...,
        tags: list[str] | None = ...,
        timeout_seconds: float | None = ...,
    ) -> Any: ...

    # TODO Make expected_return mandatory and remove above overloads.
    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        expected_return: type[Return] | None = None,  # noqa: ARG002
        context: InfrahubContext | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        timeout_seconds: float | None = None,
    ) -> Any:
        flow_func = workflow.load_function()
        parameters = dict(parameters) if parameters is not None else {}
        inject_context_parameter(func=flow_func, parameters=parameters, context=context)

        response: FlowRun = await run_deployment(
            name=workflow.full_name, poll_interval=1, parameters=parameters or {}, tags=tags, timeout=timeout_seconds
        )  # type: ignore[return-value, misc]
        if not response.state:
            raise RuntimeError("Unable to read state from the response")

        # When a timeout is set and the run has still not been claimed by a worker, treat the worker
        # as unreachable instead of holding the caller (and any lock it owns) indefinitely. A run that
        # a worker has already started is left to finish on its own schedule.
        if timeout_seconds is not None and response.state.type in (StateType.SCHEDULED, StateType.PENDING):
            raise ServiceUnavailableError(
                f"Workflow {workflow.full_name} was not picked up by a worker within {timeout_seconds} seconds"
            )

        if not response.state.is_final():
            response = await wait_for_flow_run(flow_run_id=response.id, timeout=None, poll_interval=1)
            if not response.state:
                raise RuntimeError("Unable to read state from the response")

        if response.state.type == StateType.CRASHED:
            raise RuntimeError(response.state.message)

        return await response.state.result(raise_on_failure=True)

    async def submit_workflow(
        self,
        workflow: WorkflowDefinition,
        context: InfrahubContext | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> WorkflowInfo:
        flow_func = workflow.load_function()
        parameters = dict(parameters) if parameters is not None else {}
        inject_context_parameter(func=flow_func, parameters=parameters, context=context)

        tls_insecure = config.SETTINGS.http.tls_insecure
        tls_ca_bundle = config.SETTINGS.http.tls_ca_bundle
        tls_context = self._tls_registry.get(insecure=tls_insecure, ca_bundle=tls_ca_bundle)
        async with AsyncClientContext(httpx_settings={"verify": tls_context}):
            flow_run = await run_deployment(name=workflow.full_name, timeout=0, parameters=parameters or {}, tags=tags)  # type: ignore[return-value, misc]
        return WorkflowInfo.from_flow(flow_run=flow_run)
