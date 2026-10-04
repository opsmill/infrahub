from __future__ import annotations

import logging
from datetime import UTC, timedelta
from typing import TYPE_CHECKING

import typer
from infrahub_sdk.async_typer import AsyncTyper
from prefect.client.orchestration import get_client
from prefect.client.schemas.objects import StateType
from rich.filesize import decimal

from infrahub import config
from infrahub.core.migrations.shared import get_migration_console
from infrahub.prefect_server.task_history import CleanupJob, CleanupRewrite
from infrahub.services.adapters.workflow.worker import WorkflowWorkerExecution
from infrahub.task_manager.flow_run.cleanup import POLL_INTERVAL, TaskHistoryCleanupError, run_task_history_cleanup
from infrahub.task_manager.flow_run.prefect_client import PrefectClientAdapter
from infrahub.task_manager.flow_run.retention import FlowRunRetention
from infrahub.tasks.dummy import DUMMY_FLOW, DummyInput
from infrahub.workers.dependencies import build_tls_registry
from infrahub.workflows.initialization import setup_task_manager  # noqa: TID251 - the CLI runs the one-off setup itself
from infrahub.workflows.models import WorkerPoolDefinition

from .constants import ERROR_BADGE

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient
    from rich.console import Console

app = AsyncTyper()

# States a flow run can be stuck in: RUNNING for a worker that died mid-flow, PENDING for one
# that was picked up but never got to start.
STALE_FLOW_RUN_STATES = [StateType.RUNNING, StateType.PENDING]

TASK_HISTORY_CLEANUP_NOT_PROVIDED = "The task manager does not provide the task history cleanup yet; skipped."


@app.command()
async def init(
    ctx: typer.Context,  # noqa: ARG001
    debug: bool = typer.Option(False, help="Enable advanced logging and troubleshooting"),  # noqa: ARG001
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
) -> None:
    """Initialize the task manager."""
    logging.getLogger("prefect").setLevel(logging.ERROR)

    config.load_and_exit(config_file_name=config_file)

    await setup_task_manager()


@app.command()
async def execute(
    ctx: typer.Context,  # noqa: ARG001
    debug: bool = typer.Option(False, help="Enable advanced logging and troubleshooting"),  # noqa: ARG001
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
) -> None:
    """Check the current format of the internal graph and apply the necessary migrations."""
    logging.getLogger("infrahub").setLevel(logging.WARNING)
    logging.getLogger("neo4j").setLevel(logging.ERROR)
    logging.getLogger("prefect").setLevel(logging.ERROR)

    config.load_and_exit(config_file_name=config_file)

    async with get_client(sync_client=False) as client:
        worker = WorkflowWorkerExecution(tls_registry=build_tls_registry())
        await DUMMY_FLOW.save(
            client=client, work_pool=WorkerPoolDefinition(name="infrahub-worker", worker_type="infrahubasync")
        )

        result = await worker.execute_workflow(
            workflow=DUMMY_FLOW, parameters={"data": DummyInput(firstname="John", lastname="Doe")}
        )  # type: ignore[var-annotated]
        print(result)


flush_app = AsyncTyper()

app.add_typer(flush_app, name="flush")


async def clean_task_history(
    client: PrefectClient, rewrite: CleanupRewrite, console: Console, poll_interval: timedelta = POLL_INTERVAL
) -> None:
    """Run a task history cleanup in the task manager, printing its progress and then its outcome.

    Raises:
        TaskHistoryCleanupError: When the cleanup fails, or the task manager stays unable to run it.

    """
    job = await run_task_history_cleanup(
        client=client,
        rewrite=rewrite,
        on_progress=lambda progress: console.log(_progress_line(job=progress)),
        poll_interval=poll_interval,
    )
    if job is None:
        console.log(TASK_HISTORY_CLEANUP_NOT_PROVIDED)
        return
    for line in _summary_lines(job=job):
        console.log(line)


async def flush_old_flow_runs(
    client: PrefectClient, rewrite: bool, console: Console, poll_interval: timedelta = POLL_INTERVAL
) -> int:
    """Delete the finished runs older than the task history retention, returning the exit code of the command."""
    try:
        await clean_task_history(
            client=client,
            rewrite=CleanupRewrite.ALWAYS if rewrite else CleanupRewrite.NEVER,
            console=console,
            poll_interval=poll_interval,
        )
    except TaskHistoryCleanupError as exc:
        console.log(f"{ERROR_BADGE} {exc.message}")
        return 1
    return 0


def _runs(count: int) -> str:
    return f"{count} run" if count == 1 else f"{count} runs"


def _progress_line(job: CleanupJob) -> str:
    return f"Deleting the runs that ended on {job.current_day}, {_runs(job.deleted_runs)} deleted so far"


def _summary_lines(job: CleanupJob) -> list[str]:
    lines = [f"Deleted {_runs(job.deleted_runs)} that ended before {job.cutoff.astimezone(UTC):%Y-%m-%d %H:%M} UTC"]
    if job.size_before is not None and job.size_after is not None:
        lines.append(f"Task history tables: {decimal(job.size_before)} before, {decimal(job.size_after)} after")
    if not job.rewritten:
        lines.append("Task history tables not rewritten")
    elif job.not_rewritten:
        lines.append(f"Task history tables rewritten, except {', '.join(job.not_rewritten)}, which stayed locked")
    else:
        lines.append("Task history tables rewritten")
    return lines


@flush_app.command()
async def flow_runs(
    ctx: typer.Context,  # noqa: ARG001
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
    rewrite: bool = typer.Option(
        False,
        "--rewrite",
        help=(
            "Rewrite the task history tables after the deletes, to return their disk space. "
            "Each table is locked while it is rewritten, so run it in a maintenance window."
        ),
    ),
) -> None:
    """Delete the finished task runs older than the task history retention, with their logs and artifacts.

    Raises:
        typer.Exit: With code 1 when the cleanup fails.

    """
    logging.getLogger("infrahub").setLevel(logging.WARNING)
    logging.getLogger("neo4j").setLevel(logging.ERROR)
    logging.getLogger("prefect").setLevel(logging.ERROR)

    config.load_and_exit(config_file_name=config_file)

    async with get_client(sync_client=False) as client:
        exit_code = await flush_old_flow_runs(client=client, rewrite=rewrite, console=get_migration_console())
    if exit_code:
        raise typer.Exit(exit_code)


@flush_app.command()
async def stale_runs(
    ctx: typer.Context,  # noqa: ARG001
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
    days_to_keep: int = 2,
    batch_size: int = 100,
) -> None:
    """Flush stale task runs, marking long RUNNING or PENDING flow runs as crashed."""
    logging.getLogger("infrahub").setLevel(logging.WARNING)
    logging.getLogger("neo4j").setLevel(logging.ERROR)
    logging.getLogger("prefect").setLevel(logging.ERROR)

    config.load_and_exit(config_file_name=config_file)

    async with get_client(sync_client=False) as client:
        await FlowRunRetention(client=PrefectClientAdapter(client)).purge(
            states=STALE_FLOW_RUN_STATES, delete=False, days_to_keep=days_to_keep, batch_size=batch_size
        )
