from __future__ import annotations

from typing import TYPE_CHECKING, Any, overload

from prefect.client.schemas.objects import StateType
from prefect.context import AsyncClientContext
from prefect.deployments import run_deployment

from infrahub import config, lock
from infrahub.workers.utils import inject_context_parameter
from infrahub.workflows.initialization import (
    mark_task_manager_setup_completed,
    setup_task_manager,
    setup_task_manager_identifiers,
    wait_for_task_manager,
    wait_for_task_manager_setup,
)
from infrahub.workflows.models import WorkflowInfo

from . import InfrahubWorkflow, Return

if TYPE_CHECKING:
    from prefect.client.schemas.objects import FlowRun

    from infrahub.context import InfrahubContext
    from infrahub.events.models import EventContext
    from infrahub.tls.registry import TlsContextRegistry
    from infrahub.workflows.models import WorkflowDefinition


class WorkflowWorkerExecution(InfrahubWorkflow):
    def __init__(self, tls_registry: TlsContextRegistry) -> None:
        self._tls_registry = tls_registry

    @staticmethod
    async def initialize(component_is_primary_server: bool, is_initial_setup: bool = False) -> None:
        # The primary server ensures the task-manager deployments and triggers exist on every boot,
        # not only on first-time initialization: a database restored from a snapshot has no
        # first-time init (Root already exists) but still starts against a fresh task manager whose
        # display-label/HFID triggers were never registered. Both setup flows are idempotent
        # (force_update=True), so re-running them on a normal restart is safe.
        if is_initial_setup or component_is_primary_server:
            # The task manager may still be booting (its startup dependency is relaxed so schema load
            # can overlap it); wait for its API before registering deployments and triggers.
            await wait_for_task_manager()
            await WorkflowWorkerExecution._setup_task_manager()
            await setup_task_manager_identifiers()
            await mark_task_manager_setup_completed()
        else:
            # Only one worker performs the registration, but every worker starts serving (and can
            # receive a request that dispatches a workflow run) the moment its own startup
            # completes. Block here until the registration is marked complete so no worker accepts
            # traffic against a task manager that is missing the deployments and triggers.
            await wait_for_task_manager_setup()

    @staticmethod
    async def _setup_task_manager() -> None:
        async with lock.registry.get(name=lock.GLOBAL_WORKER_TASKMGR_INIT_LOCK):
            await setup_task_manager()

    @overload
    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        expected_return: type[Return],
        context: InfrahubContext | EventContext | None = None,
        parameters: dict[str, Any] | None = ...,
        tags: list[str] | None = ...,
    ) -> Return: ...

    @overload
    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        expected_return: None = ...,
        context: InfrahubContext | EventContext | None = ...,
        parameters: dict[str, Any] | None = ...,
        tags: list[str] | None = ...,
    ) -> Any: ...

    # TODO Make expected_return mandatory and remove above overloads.
    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        expected_return: type[Return] | None = None,  # noqa: ARG002
        context: InfrahubContext | EventContext | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Any:
        flow_func = workflow.load_function()
        parameters = dict(parameters) if parameters is not None else {}
        inject_context_parameter(func=flow_func, parameters=parameters, context=context)

        response: FlowRun = await run_deployment(
            name=workflow.full_name, poll_interval=1, parameters=parameters or {}, tags=tags
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
    ) -> WorkflowInfo:
        flow_func = workflow.load_function()
        parameters = dict(parameters) if parameters is not None else {}
        inject_context_parameter(func=flow_func, parameters=parameters, context=context)

        tls_insecure = config.SETTINGS.http.tls_insecure
        tls_ca_bundle = config.SETTINGS.http.tls_ca_bundle
        tls_context = self._tls_registry.get(insecure=tls_insecure, ca_bundle=tls_ca_bundle)
        async with AsyncClientContext(httpx_settings={"verify": tls_context}):
            flow_run = await run_deployment(name=workflow.full_name, timeout=0, parameters=parameters or {}, tags=tags)  # type: ignore[misc]
        return WorkflowInfo.from_flow(flow_run=flow_run)
