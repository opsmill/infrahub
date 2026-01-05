import asyncio
import contextlib
import logging
import os
from pathlib import Path
from typing import Any

import typer
from anyio.abc import TaskStatus
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.exceptions import Error as SdkError
from prefect import settings as prefect_settings
from prefect.client.schemas.objects import FlowRun
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

    async def setup(
        self,
        client: InfrahubClient | None = None,
        metric_port: int | None = None,
        **kwargs: dict[str, Any],
    ) -> None:
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
        self._logger.info("Worker initialization completed .. ")

    async def run(
        self,
        flow_run: FlowRun,
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
            client = InfrahubClient(
                config=Config(address=config.SETTINGS.main.internal_address, retry_on_failure=True, log=self._logger)
            )

        try:
            await client.branch.all()
        except SdkError as err:
            self._logger.error(f"Error in communication with Infrahub: {err.message}")
            raise typer.Exit(1) from err

        return client

    async def _init_services(self, client: InfrahubClient) -> None:
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
