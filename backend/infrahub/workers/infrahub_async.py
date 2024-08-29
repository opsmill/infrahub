import importlib
import logging
from typing import Any, Optional

import typer
from anyio.abc import TaskStatus
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.exceptions import Error as SdkError
from prefect.client.schemas.objects import FlowRun
from prefect.flow_engine import run_flow_async
from prefect.workers.base import BaseJobConfiguration, BaseVariables, BaseWorker, BaseWorkerResult

from infrahub import config
from infrahub.components import ComponentType
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


class InfrahubWorkerAsyncConfiguration(BaseJobConfiguration):
    pass


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
    _description = "My worker description."

    async def setup(self, **kwargs: dict[str, Any]) -> None:
        await super().setup(**kwargs)

        logging.getLogger("websockets").setLevel(logging.ERROR)
        logging.getLogger("httpx").setLevel(logging.ERROR)
        logging.getLogger("httpcore").setLevel(logging.ERROR)
        logging.getLogger("neo4j").setLevel(logging.ERROR)
        logging.getLogger("aio_pika").setLevel(logging.ERROR)
        logging.getLogger("aiormq").setLevel(logging.ERROR)
        logging.getLogger("git").setLevel(logging.ERROR)

        config.load_and_exit()

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
            component_type=ComponentType.GIT_AGENT,
        )
        services.service = service

        await service.initialize()

        # Initialize the lock
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

        # exit_code = job_status.exit_code if job_status else -1 # Get result of execution for reporting
        return InfrahubWorkerAsyncResult(
            status_code=0,
            identifier=str(flow_run.id),
        )
