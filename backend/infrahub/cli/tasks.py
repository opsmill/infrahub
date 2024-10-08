import logging

import typer
from infrahub_sdk.async_typer import AsyncTyper
from prefect.client.orchestration import get_client

from infrahub import config
from infrahub.services.adapters.workflow.worker import WorkflowWorkerExecution
from infrahub.tasks.dummy import DUMMY_FLOW, DummyInput
from infrahub.workflows.initialization import setup_task_manager
from infrahub.workflows.models import WorkerPoolDefinition

app = AsyncTyper()

# pylint: disable=unused-argument


@app.command()
async def init(
    ctx: typer.Context,
    debug: bool = typer.Option(False, help="Enable advanced logging and troubleshooting"),
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
) -> None:
    """Initialize the task manager"""
    logging.getLogger("prefect").setLevel(logging.ERROR)

    config.load_and_exit(config_file_name=config_file)

    await setup_task_manager()


@app.command()
async def execute(
    ctx: typer.Context,
    debug: bool = typer.Option(False, help="Enable advanced logging and troubleshooting"),
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
) -> None:
    """Check the current format of the internal graph and apply the necessary migrations"""
    logging.getLogger("infrahub").setLevel(logging.WARNING)
    logging.getLogger("neo4j").setLevel(logging.ERROR)
    logging.getLogger("prefect").setLevel(logging.ERROR)

    config.load_and_exit(config_file_name=config_file)

    async with get_client(sync_client=False) as client:
        worker = WorkflowWorkerExecution()
        await DUMMY_FLOW.save(client=client, work_pool=WorkerPoolDefinition(name="testing", worker_type="process"))

        result = await worker.execute(workflow=DUMMY_FLOW, data=DummyInput(firstname="John", lastname="Doe"))  # type: ignore[var-annotated]
        print(result)
