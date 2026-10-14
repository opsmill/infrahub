from __future__ import annotations

import asyncio
import logging
from datetime import UTC, timedelta
from typing import TYPE_CHECKING

import httpx
import typer
from infrahub_sdk.async_typer import AsyncTyper
from prefect.client.orchestration import get_client
from prefect.client.schemas.objects import StateType
from pydantic import ValidationError
from rich.filesize import decimal

from infrahub import config
from infrahub.core.migrations.shared import get_migration_console
from infrahub.prefect_server.task_history_models import CleanupJob, CleanupRewrite, TaskHistorySize
from infrahub.services.adapters.workflow.worker import WorkflowWorkerExecution
from infrahub.task_manager.flow_run.cleanup import (
    POLL_INTERVAL,
    TaskHistoryCleanupError,
    TaskHistoryCleanupFailedError,
    read_task_history_size,
    run_task_history_cleanup,
)
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
TASK_HISTORY_REWRITE_COMMAND = "infrahub tasks flush flow-runs --rewrite"
# Short, because the size only informs the hint and is not worth a long wait.
TASK_HISTORY_SIZE_TIMEOUT = timedelta(seconds=10)


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


async def task_history_size_hint(
    client: PrefectClient, answer_within: timedelta = TASK_HISTORY_SIZE_TIMEOUT
) -> str | None:
    """Return the disk space the task history takes and the command that returns it, or None on SQLite."""
    try:
        async with asyncio.timeout(answer_within.total_seconds()):
            measured = await read_task_history_size(client=client)
    # The size only informs the hint, so a failure to read it is named and the command is given without it.
    except (httpx.HTTPError, ValidationError, TimeoutError) as exc:
        return (
            f"Could not read the task history size from the task manager ({type(exc).__name__}). "
            f"To get the disk space of old task history back, run: {TASK_HISTORY_REWRITE_COMMAND}"
        )
    if measured.size is None:
        return None
    return (
        f"Task history takes {decimal(measured.size)}, with {_old_runs(measured=measured)} older than the retention. "
        f"To get the space back, run: {TASK_HISTORY_REWRITE_COMMAND}"
    )


def _old_runs(measured: TaskHistorySize) -> str:
    if measured.old_runs_limit_reached:
        return f"more than {measured.old_runs:,} runs"
    if measured.old_runs == 0:
        return "no runs"
    return f"{measured.old_runs:,} run" if measured.old_runs == 1 else f"{measured.old_runs:,} runs"


async def flush_old_flow_runs(
    client: PrefectClient, rewrite: bool, console: Console, poll_interval: timedelta = POLL_INTERVAL
) -> int:
    """Delete the finished runs older than the task history retention, printing the progress, waits and outcome.

    Returns:
        The exit code of the command.

    """
    try:
        job = await run_task_history_cleanup(
            client=client,
            rewrite=CleanupRewrite.IF_FREED if rewrite else CleanupRewrite.NEVER,
            on_progress=lambda progress: console.log(_progress_line(job=progress)),
            on_wait=lambda wait: console.log(f"Waiting to start the cleanup, because {wait.reason}"),
            poll_interval=poll_interval,
        )
    except TaskHistoryCleanupFailedError as exc:
        console.log(f"{ERROR_BADGE} {exc.message}")
        for line in _committed_lines(job=exc.job):
            console.log(line)
        return 1
    except TaskHistoryCleanupError as exc:
        console.log(f"{ERROR_BADGE} {exc.message}")
        return 1
    except httpx.HTTPError as exc:
        console.log(f"{ERROR_BADGE} {type(exc).__name__}: {exc}")
        return 1
    if job is None:
        console.log(TASK_HISTORY_CLEANUP_NOT_PROVIDED)
        return 0
    for line in _summary_lines(job=job):
        console.log(line)
    return 0


def _runs(count: int) -> str:
    return f"{count} run" if count == 1 else f"{count} runs"


def _progress_line(job: CleanupJob) -> str:
    return f"Deleting the runs that ended on {job.current_day}, {_runs(job.deleted_runs)} deleted so far"


def _rewrite_lines(job: CleanupJob) -> list[str]:
    """What the rewrite did with each table, which a job records only once its rewrite finished."""
    lines: list[str] = []
    if job.rewritten:
        lines.append(f"Rewrote {', '.join(job.rewritten)}")
    if job.mostly_live:
        lines.append(
            f"Left {', '.join(job.mostly_live)} as they are, because their live rows hold at least half of their disk space"
        )
    if job.not_rewritten:
        lines.append(f"Did not rewrite {', '.join(job.not_rewritten)}, which stayed locked by other sessions")
    return lines


def _committed_lines(job: CleanupJob) -> list[str]:
    """The runs a failed cleanup deleted, and the tables it rewrote."""
    return [f"Deleted {_runs(job.deleted_runs)} before the failure", *_rewrite_lines(job=job)]


def _summary_lines(job: CleanupJob) -> list[str]:
    lines = [f"Deleted {_runs(job.deleted_runs)} that ended before {job.cutoff.astimezone(UTC):%Y-%m-%d %H:%M} UTC"]
    if job.size_before is not None and job.size_after is not None:
        lines.append(
            f"Task history and activity log tables: {decimal(job.size_before)} before, {decimal(job.size_after)} after"
        )
    if job.rewrite is CleanupRewrite.NEVER:
        lines.append("Tables not rewritten")
    else:
        lines.extend(_rewrite_lines(job=job) or ["No table rewritten"])
    return lines


@flush_app.command()
async def flow_runs(
    ctx: typer.Context,  # noqa: ARG001
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
    rewrite: bool = typer.Option(
        False,
        "--rewrite",
        help=(
            "After the deletes, rewrite each task history and activity log table whose live rows hold less than "
            "half of its disk space, to return that space to the disk. Tasks that write to a table wait while it is "
            "rewritten."
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
