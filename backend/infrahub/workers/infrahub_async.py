import importlib
import logging
import os
from typing import Any, Optional

import typer
from anyio.abc import TaskStatus
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.exceptions import Error as SdkError
from prefect import settings as prefect_settings
from prefect.client.schemas.objects import FlowRun
from prefect.flow_engine import run_flow_async
from prefect.workers.base import BaseJobConfiguration, BaseVariables, BaseWorker, BaseWorkerResult
from prometheus_client import start_http_server

from infrahub import __version__ as infrahub_version
from infrahub import config
from infrahub.components import ComponentType
from infrahub.core import registry
from infrahub.core.initialization import initialization
from infrahub.database import InfrahubDatabase, get_db
from infrahub.dependencies.registry import build_component_registry
from infrahub.git import initialize_repositories_directory
from infrahub.lock import initialize_lock
from infrahub.services import InfrahubServices, services
from infrahub.services.adapters.cache.nats import NATSCache
from infrahub.services.adapters.cache.redis import RedisCache
from infrahub.services.adapters.message_bus.nats import NATSMessageBus
from infrahub.services.adapters.message_bus.rabbitmq import RabbitMQMessageBus
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.services.adapters.workflow.worker import WorkflowWorkerExecution
from infrahub.workflows.models import TASK_RESULT_STORAGE_NAME

WORKER_QUERY_SECONDS = "2"
WORKER_PERSIST_RESULT = "true"
WORKER_DEFAULT_RESULT_STORAGE_BLOCK = f"redisstoragecontainer/{TASK_RESULT_STORAGE_NAME}"


class InfrahubWorkerAsyncConfiguration(BaseJobConfiguration):
    env: dict[str, str | None] = {
        "PREFECT_WORKER_QUERY_SECONDS": WORKER_QUERY_SECONDS,
        "PREFECT_RESULTS_PERSIST_BY_DEFAULT": WORKER_PERSIST_RESULT,
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

        if not config.SETTINGS.settings:
            config_file = os.environ.get("INFRAHUB_CONFIG", "infrahub.toml")
            config.load_and_exit(config_file_name=config_file)

        # Start metric endpoint
        if metric_port is None or metric_port != 0:
            metric_port = metric_port or int(os.environ.get("INFRAHUB_METRICS_PORT", 8000))
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

        if not client:
            self._logger.debug(f"Using Infrahub API at {config.SETTINGS.main.internal_address}")
            client = InfrahubClient(
                config=Config(address=config.SETTINGS.main.internal_address, retry_on_failure=True, log=self._logger)
            )

        try:
            await client.branch.all()
        except SdkError as exc:
            self._logger.error(f"Error in communication with Infrahub: {exc.message}")
            raise typer.Exit(1)

        database = InfrahubDatabase(driver=await get_db(retry=1))

        workflow = config.OVERRIDE.workflow or (
            WorkflowWorkerExecution()
            if config.SETTINGS.workflow.driver == config.WorkflowDriver.WORKER
            else WorkflowLocalExecution()
        )

        message_bus = config.OVERRIDE.message_bus or (
            NATSMessageBus() if config.SETTINGS.broker.driver == config.BrokerDriver.NATS else RabbitMQMessageBus()
        )
        cache = config.OVERRIDE.cache or (
            NATSCache() if config.SETTINGS.cache.driver == config.CacheDriver.NATS else RedisCache()
        )

        service = InfrahubServices(
            cache=cache,
            client=client,
            database=database,
            message_bus=message_bus,
            workflow=workflow,
            component_type=ComponentType.GIT_AGENT,
        )
        services.service = service

        await service.initialize()

        if not registry.schema_has_been_initialized():
            initialize_lock(service=service)

            async with service.database.start_session() as db:
                await initialization(db=db)

            await service.component.refresh_schema_hash()

        initialize_repositories_directory()
        build_component_registry()
        self._logger.info("Worker initialization completed .. ")

    async def run(
        self,
        flow_run: FlowRun,
        configuration: BaseJobConfiguration,
        task_status: Optional[TaskStatus] = None,
    ) -> BaseWorkerResult:
        flow_run_logger = self.get_flow_run_logger(flow_run)

        entrypoint: str = configuration._related_objects["deployment"].entrypoint

        file_path, flow_name = entrypoint.split(":")
        file_path.replace("/", ".")
        module_path = file_path.replace("backend/", "").replace(".py", "").replace("/", ".")
        module = importlib.import_module(module_path)
        flow_func = getattr(module, flow_name)

        flow_run_logger.debug("Validating parameters")
        params = flow_func.validate_parameters(parameters=flow_run.parameters)

        if task_status:
            task_status.started()

        await run_flow_async(flow=flow_func, flow_run=flow_run, parameters=params, return_type="state")

        return InfrahubWorkerAsyncResult(
            status_code=0,
            identifier=str(flow_run.id),
        )
