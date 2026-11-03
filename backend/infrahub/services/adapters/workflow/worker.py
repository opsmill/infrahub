from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, overload

from httpx import HTTPStatusError, codes
from opentelemetry import trace
from opentelemetry.instrumentation.utils import is_instrumentation_enabled
from prefect.client.schemas.objects import StateType
from prefect.client.utilities import get_or_create_client
from prefect.context import AsyncClientContext, FlowRunContext, TaskRunContext
from prefect.deployments import arun_deployment
from prefect.telemetry.run_telemetry import LABELS_TRACEPARENT_KEY, RunTelemetry

from infrahub import config, lock
from infrahub.workers.utils import inject_context_parameter
from infrahub.workflows.initialization import (
    setup_task_manager,  # noqa: TID251 - worker startup owns the setup
    setup_task_manager_identifiers,
)
from infrahub.workflows.models import WorkflowInfo

from . import InfrahubWorkflow, Return
from .priority import prepare_dispatch

if TYPE_CHECKING:
    from uuid import UUID

    from prefect.client.orchestration import PrefectClient
    from prefect.client.schemas.objects import FlowRun
    from prefect.types import KeyValueLabelsField

    from infrahub.context import InfrahubContext
    from infrahub.events.models import EventContext
    from infrahub.tls.registry import TlsContextRegistry
    from infrahub.workflows.constants import WorkflowPriority
    from infrahub.workflows.models import WorkflowDefinition

POLL_INTERVAL_SECONDS = 1


def trace_labels() -> KeyValueLabelsField:
    """Return the flow run labels that carry the current trace into the dispatched run."""
    if not is_instrumentation_enabled():
        return {}
    traceparent = RunTelemetry.traceparent_from_span(span=trace.get_current_span())
    return {LABELS_TRACEPARENT_KEY: traceparent} if traceparent else {}


class WorkflowWorkerExecution(InfrahubWorkflow):
    def __init__(self, tls_registry: TlsContextRegistry) -> None:
        self._tls_registry = tls_registry
        # Task-manager setup upserts each deployment in place, so an id only changes when its deployment is deleted.
        self._deployment_ids: dict[str, UUID] = {}

    @staticmethod
    async def initialize(component_is_primary_server: bool, is_initial_setup: bool = False) -> None:
        if is_initial_setup:
            await WorkflowWorkerExecution._setup_task_manager()
            await setup_task_manager_identifiers()
        elif component_is_primary_server:
            await WorkflowWorkerExecution._setup_task_manager()

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
        dispatch_context, work_queue_name = prepare_dispatch(workflow=workflow, context=context, priority=priority)
        inject_context_parameter(func=flow_func, parameters=parameters, context=dispatch_context)

        response = await self._run_deployment(
            workflow=workflow, parameters=parameters, tags=tags, work_queue_name=work_queue_name, wait=True
        )
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
        dispatch_context, work_queue_name = prepare_dispatch(workflow=workflow, context=context, priority=priority)
        inject_context_parameter(func=flow_func, parameters=parameters, context=dispatch_context)

        tls_insecure = config.SETTINGS.http.tls_insecure
        tls_ca_bundle = config.SETTINGS.http.tls_ca_bundle
        tls_context = self._tls_registry.get(insecure=tls_insecure, ca_bundle=tls_ca_bundle)
        async with AsyncClientContext(httpx_settings={"verify": tls_context}):
            flow_run = await self._run_deployment(
                workflow=workflow, parameters=parameters, tags=tags, work_queue_name=work_queue_name, wait=False
            )
        return WorkflowInfo.from_flow(flow_run=flow_run)

    async def _run_deployment(
        self,
        workflow: WorkflowDefinition,
        parameters: dict[str, Any],
        tags: list[str] | None,
        work_queue_name: str | None,
        wait: bool,
    ) -> FlowRun:
        if FlowRunContext.get() or TaskRunContext.get():
            # Linking the run as a subflow of the calling flow or task run needs the whole deployment, read per call.
            return await arun_deployment(
                name=workflow.full_name,
                parameters=parameters,
                tags=tags,
                work_queue_name=work_queue_name,
                timeout=None if wait else 0,
                poll_interval=POLL_INTERVAL_SECONDS,
            )

        client, _ = get_or_create_client()
        flow_run = await self._create_flow_run(
            client=client, workflow=workflow, parameters=parameters, tags=tags, work_queue_name=work_queue_name
        )
        while wait and not (flow_run.state and flow_run.state.is_final()):
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            flow_run = await client.read_flow_run(flow_run_id=flow_run.id)
        return flow_run

    async def _create_flow_run(
        self,
        client: PrefectClient,
        workflow: WorkflowDefinition,
        parameters: dict[str, Any],
        tags: list[str] | None,
        work_queue_name: str | None,
    ) -> FlowRun:
        async def create(deployment_id: UUID) -> FlowRun:
            return await client.create_flow_run_from_deployment(
                deployment_id=deployment_id,
                parameters=parameters,
                tags=tags,
                work_queue_name=work_queue_name,
                labels=trace_labels(),
            )

        cached_id = self._deployment_ids.get(workflow.full_name)
        if cached_id is not None:
            try:
                return await create(deployment_id=cached_id)
            except HTTPStatusError as exc:
                # A deployment deleted and saved again under the same name has a new id.
                if exc.response.status_code != codes.NOT_FOUND:
                    raise

        deployment = await client.read_deployment_by_name(name=workflow.full_name)
        self._deployment_ids[workflow.full_name] = deployment.id
        return await create(deployment_id=deployment.id)
