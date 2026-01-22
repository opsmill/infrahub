import asyncio
import contextlib
import logging
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

import typer
from anyio.abc import TaskStatus
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.exceptions import Error as SdkError
from prefect import settings as prefect_settings
from prefect.context import AsyncClientContext
from prefect.flow_engine import run_flow_async
from prefect.logging.handlers import APILogHandler
from prefect.workers.base import BaseJobConfiguration, BaseVariables, BaseWorker, BaseWorkerResult
from prometheus_client import start_http_server

from infrahub import __version__ as infrahub_version
from infrahub import config
from infrahub.components import ComponentType
from infrahub.core import registry
from infrahub.core.initialization import initialization
from infrahub.database.graph import validate_graph_version
from infrahub.dependencies.registry import build_component_registry
from infrahub.exceptions import InitializationError
from infrahub.git import initialize_repositories_directory
from infrahub.lock import initialize_lock
from infrahub.services import InfrahubServices
from infrahub.trace import configure_trace
from infrahub.workers.dependencies import (
    get_cache,
    get_component,
    get_database,
    get_http,
    get_message_bus,
    get_workflow,
    set_component_type,
)
from infrahub.workers.utils import inject_service_parameter, load_flow_function
from infrahub.workflows.models import TASK_RESULT_STORAGE_NAME

if TYPE_CHECKING:
    from prefect.client.schemas.objects import FlowRun
    from prefect.client.schemas.responses import WorkerFlowRunResponse

WORKER_QUERY_SECONDS = "2"
WORKER_DEFAULT_RESULT_STORAGE_BLOCK = f"redisstoragecontainer/{TASK_RESULT_STORAGE_NAME}"
DEFAULT_TASK_LOGGERS = ["infrahub.tasks"]


class InfrahubWorkerAsyncConfiguration(BaseJobConfiguration):
    env: dict[str, str | None] = {
        "PREFECT_WORKER_QUERY_SECONDS": WORKER_QUERY_SECONDS,
        "PREFECT_DEFAULT_RESULT_STORAGE_BLOCK": WORKER_DEFAULT_RESULT_STORAGE_BLOCK,
    }
    labels: dict[str, str] = {
        "infrahub.app/version": infrahub_version,
    }


class InfrahubWorkerAsyncTemplateVariables(BaseVariables):
    pass


class InfrahubWorkerAsyncResult(BaseWorkerResult):
    """Result returned by the InfrahubWorker."""


class InfrahubWorkerAsync(BaseWorker):
    type: str = "infrahubasync"
    job_configuration = InfrahubWorkerAsyncConfiguration
    job_configuration_variables = InfrahubWorkerAsyncTemplateVariables
    _documentation_url = "https://example.com/docs"
    _logo_url = "https://example.com/logo"
    _description = "Infrahub worker designed to run the flow in the main async loop."
    service: InfrahubServices  # keep a reference to `service` so we can inject it within flows parameters.
    component_type = ComponentType.GIT_AGENT
    _flow_run_gcl_locks: dict[
        str, tuple[str, float]
    ]  # Track GCL names acquired per flow run (flow_run_id -> list of GCL names)

    async def setup(
        self,
        client: InfrahubClient | None = None,
        metric_port: int | None = None,
        **kwargs: dict[str, Any],
    ) -> None:
        # Initialize the dict to track GCL locks acquired for flow runs
        self._flow_run_gcl_locks = {}

        logging.getLogger("websockets").setLevel(logging.ERROR)
        logging.getLogger("httpx").setLevel(logging.ERROR)
        logging.getLogger("httpcore").setLevel(logging.ERROR)
        logging.getLogger("neo4j").setLevel(logging.ERROR)
        logging.getLogger("aio_pika").setLevel(logging.ERROR)
        logging.getLogger("aiormq").setLevel(logging.ERROR)
        logging.getLogger("git").setLevel(logging.ERROR)
        # Prevent git from interactively prompting the user for passwords if the credentials provided
        # by the credential helper is failing.
        os.environ["GIT_TERMINAL_PROMPT"] = "0"

        if not config.SETTINGS.settings:
            config_file = os.environ.get("INFRAHUB_CONFIG", "infrahub.toml")
            config.load_and_exit(config_file_name=config_file)

        self._init_logger()

        # Initialize trace
        if config.SETTINGS.trace.enable:
            configure_trace(
                service="infrahub-task-worker",
                version=infrahub_version,
                exporter_type=config.SETTINGS.trace.exporter_type,
                exporter_endpoint=config.SETTINGS.trace.exporter_endpoint,
                exporter_protocol=config.SETTINGS.trace.exporter_protocol,
            )

        # Start metric endpoint
        if metric_port is None or metric_port != 0:
            metric_port = metric_port or int(os.environ.get("INFRAHUB_METRICS_PORT", "8000"))
            self._logger.info(f"Starting metric endpoint on port {metric_port}")
            start_http_server(metric_port)

        await super().setup(**kwargs)

        self._exit_stack.enter_context(
            prefect_settings.temporary_settings(
                updates={  # type: ignore[arg-type]
                    prefect_settings.PREFECT_WORKER_QUERY_SECONDS: config.SETTINGS.workflow.worker_polling_interval,
                    prefect_settings.PREFECT_RESULTS_PERSIST_BY_DEFAULT: True,
                    prefect_settings.PREFECT_DEFAULT_RESULT_STORAGE_BLOCK: WORKER_DEFAULT_RESULT_STORAGE_BLOCK,
                }
            )
        )

        set_component_type(component_type=self.component_type)
        await self.set_git_global_config()
        await self._init_services(client=client)

        if not registry.schema_has_been_initialized():
            initialize_lock(service=self.service)

            async with self.service.database.start_session() as db:
                await initialization(db=db)

            await self.service.component.refresh_schema_hash()

        async with self.service.database.start_session() as dbs:
            await validate_graph_version(db=dbs)

        initialize_repositories_directory()
        build_component_registry()
        await self.service.scheduler.start_schedule()
        await self._create_worker_gcls()
        self._logger.info("Worker initialization completed .. ")

    async def run(
        self,
        flow_run: "FlowRun",
        configuration: BaseJobConfiguration,
        task_status: TaskStatus[int] | None = None,
    ) -> BaseWorkerResult:
        flow_run_logger = self.get_flow_run_logger(flow_run)

        entrypoint: str = configuration._related_objects["deployment"].entrypoint

        file_path, flow_name = entrypoint.split(":")
        module_path = file_path.removeprefix("backend/").removesuffix(".py").replace("/", ".")
        flow_func = load_flow_function(module_path=module_path, flow_name=flow_name)
        inject_service_parameter(func=flow_func, parameters=flow_run.parameters, service=self.service)
        flow_run_logger.debug("Validating parameters")
        params = flow_func.validate_parameters(parameters=flow_run.parameters)

        if task_status:
            task_status.started(True)

        async with AsyncClientContext(httpx_settings={"verify": get_http().verify_tls()}) as ctx:
            ctx._httpx_settings = None  # Hack to make all child task/flow runs use the same client
            await run_flow_async(flow=flow_func, flow_run=flow_run, parameters=params, return_type="state")

        return InfrahubWorkerAsyncResult(status_code=0, identifier=str(flow_run.id))

    def _init_logger(self) -> None:
        """Initialize loggers to use the API handle provided by Prefect."""
        api_handler = APILogHandler()

        for logger_name in config.SETTINGS.workflow.extra_loggers + DEFAULT_TASK_LOGGERS:
            logger = logging.getLogger(logger_name)
            logger.setLevel(config.SETTINGS.workflow.extra_log_level.value)
            logger.addHandler(api_handler)

    async def _init_infrahub_client(self, client: InfrahubClient | None = None) -> InfrahubClient:
        if not client:
            self._logger.debug(f"Using Infrahub API at {config.SETTINGS.main.internal_address}")
            try:
                client = InfrahubClient(
                    config=Config(
                        address=config.SETTINGS.main.infrahub_address, retry_on_failure=True, log=self._logger
                    )
                )
            except InitializationError as err:
                self._logger.error(
                    "Infrahub client initialization failed due to missing configuration for internal_address."
                )
                raise typer.Exit(1) from err

        try:
            await client.branch.all()
        except SdkError as err:
            self._logger.error(f"Error in communication with Infrahub: {err.message}")
            raise typer.Exit(1) from err

        return client

    async def _init_services(self, client: InfrahubClient | None) -> None:
        client = await self._init_infrahub_client(client=client)

        service = await InfrahubServices.new(
            cache=await get_cache(),
            client=client,
            database=await get_database(),
            message_bus=await get_message_bus(),
            workflow=get_workflow(),
            component=await get_component(),
            component_type=self.component_type,
        )

        self.service = service

    async def _create_worker_gcls(self) -> None:
        """Create Global Concurrency Limits for this worker."""
        from prefect.client.orchestration import get_client as get_prefect_client

        from infrahub.workflows.locks import PER_WORKER_GCLS

        try:
            async with get_prefect_client(sync_client=False) as client:
                for gcl_def in PER_WORKER_GCLS:
                    await gcl_def.create(client)
                    self._logger.info(f"Created global concurrency limit: {gcl_def.get_name()}")
        except Exception as exc:
            self._logger.warning(f"Failed to create global concurrency limits: {exc}")

    async def _submit_scheduled_flow_runs(self, flow_run_response: list["WorkerFlowRunResponse"]) -> list["FlowRun"]:
        """Override to acquire per-worker GCL locks BEFORE submitting flows.

        Lock is held for the duration of flow execution and released in
        _submit_run_and_capture_errors finally block. This ensures other workers
        can pick up batches if this worker is already processing one.
        """
        from prefect.concurrency._asyncio import aacquire_concurrency_slots

        from infrahub.workflows.locks import COMPUTED_ATTR_BATCH_GCL

        filtered_response = []
        for entry in flow_run_response:
            flow_run = entry.flow_run

            # Check if this flow requires per-worker GCL
            if self._flow_requires_worker_gcl(flow_run):
                gcl_name = COMPUTED_ATTR_BATCH_GCL.get_name()
                try:
                    # Try to acquire slot
                    acquired = await aacquire_concurrency_slots(
                        names=[gcl_name],
                        slots=1,
                        mode="concurrency",
                        strict=True,
                        timeout_seconds=1,  # short timeout to avoid blocking
                    )
                    if not acquired:
                        self._logger.info(f"Skipping flow {flow_run.id}: GCL {gcl_name} is held")
                        continue
                    # Store the GCL name and acquisition time for release after flow execution
                    self._flow_run_gcl_locks[flow_run.id] = (gcl_name, time.time())
                    self._logger.info(f"Acquired GCL {gcl_name} for flow {flow_run.id}")
                except Exception as exc:
                    self._logger.info(f"Skipping flow {flow_run.id}: GCL acquisition failed: {exc}")
                    continue

            filtered_response.append(entry)

        return await super()._submit_scheduled_flow_runs(filtered_response)

    def _flow_requires_worker_gcl(self, flow_run: "FlowRun") -> bool:
        """Check if this flow run requires per-worker GCL check based on tags."""
        from infrahub.workflows.constants import WorkflowTag

        if flow_run.tags:
            return WorkflowTag.REQUIRES_WORKER_GCL.render() in flow_run.tags
        return False

    async def _submit_run_and_capture_errors(
        self,
        flow_run: "FlowRun",
        task_status: TaskStatus[int | Exception] | None = None,
    ) -> BaseWorkerResult | Exception:
        """Override to release GCL locks in finally block."""
        try:
            return await super()._submit_run_and_capture_errors(flow_run, task_status)
        finally:
            # Release any GCL locks acquired for this flow run
            await self._release_flow_run_gcl_locks(flow_run.id)

    async def _release_flow_run_gcl_locks(self, flow_run_id: UUID) -> None:
        """Release GCL locks acquired for a flow run."""
        from prefect.concurrency._asyncio import arelease_concurrency_slots

        if flow_run_id not in self._flow_run_gcl_locks:
            return

        gcl_name, acquisition_time = self._flow_run_gcl_locks.pop(flow_run_id)
        try:
            await arelease_concurrency_slots(
                names=[gcl_name], slots=1, occupancy_seconds=time.time() - acquisition_time
            )
            self._logger.debug(f"Released GCL lock {gcl_name} for flow {flow_run_id}")
        except Exception as exc:
            self._logger.warning(f"Failed to release GCL lock for flow {flow_run_id}: {exc}")

    async def teardown(self, *exc_info: Any) -> None:
        """Override to clean up GCL locks on shutdown."""
        from prefect.concurrency._asyncio import arelease_concurrency_slots

        # Release any remaining GCL locks
        for flow_run_id, (gcl_name, acquisition_time) in list(self._flow_run_gcl_locks.items()):
            try:
                await arelease_concurrency_slots(
                    names=[gcl_name], slots=1, occupancy_seconds=time.time() - acquisition_time
                )
                self._logger.debug(f"Released GCL lock {gcl_name} for flow {flow_run_id} during teardown")
            except Exception as exc:
                self._logger.warning(f"Failed to release GCL lock for flow {flow_run_id}: {exc}")
        self._flow_run_gcl_locks.clear()

        await super().teardown(*exc_info)

    async def set_git_global_config(self) -> None:
        global_config_file = config.SETTINGS.git.global_config_file
        if not os.getenv("GIT_CONFIG_GLOBAL") and global_config_file:
            config_dir = Path(global_config_file).parent
            with contextlib.suppress(FileExistsError):
                config_dir.mkdir(exist_ok=True, parents=True)
            os.environ["GIT_CONFIG_GLOBAL"] = global_config_file
            self._logger.info(f"Set git config file to {global_config_file}")

        await self._run_git_config_global(config.SETTINGS.git.user_name, setting_name="user.name")
        await self._run_git_config_global(config.SETTINGS.git.user_email, setting_name="user.email")
        await self._run_git_config_global("*", "--replace-all", setting_name="safe.directory")
        await self._run_git_config_global("true", setting_name="credential.usehttppath")
        await self._run_git_config_global(
            f"/usr/bin/env {config.SETTINGS.dev.git_credential_helper}", setting_name="credential.helper"
        )

    async def _run_git_config_global(self, *args: str, setting_name: str) -> None:
        proc = await asyncio.create_subprocess_exec(
            "git",
            "config",
            "--global",
            setting_name,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            error_msg = stderr.decode("utf-8", errors="ignore").strip() or "unknown error"
            self._logger.error(f"Failed to set git {setting_name}: %s", error_msg)
        else:
            self._logger.info(f"Git {setting_name} set")
