from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import typer
from click.core import ParameterSource
from infrahub_sdk.async_typer import AsyncTyper
from prefect.client.orchestration import get_client
from prefect.client.schemas.objects import StateType
from pydantic import ValidationError
from rich.filesize import decimal

from infrahub import config
from infrahub.core.migrations.shared import get_migration_console
from infrahub.prefect_server.app import apply_infrahub_settings_to_prefect
from infrahub.prefect_server.task_history_models import CleanupJob, CleanupRewrite, TaskHistorySize
from infrahub.services.adapters.workflow.worker import WorkflowWorkerExecution
from infrahub.task_manager.flow_run.cleanup import (
    GIVE_UP_AFTER,
    POLL_INTERVAL,
    FollowedCleanup,
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
    from collections.abc import Callable

    from prefect.client.orchestration import PrefectClient
    from rich.console import Console

app = AsyncTyper()


@app.callback()
def callback() -> None:
    """Manage the task manager and its task history."""


# States a flow run can be stuck in: RUNNING for a worker that died mid-flow, PENDING for one
# that was picked up but never got to start.
STALE_FLOW_RUN_STATES = [StateType.RUNNING, StateType.PENDING]

TASK_HISTORY_CLEANUP_NOT_PROVIDED = "The task manager does not provide the task history cleanup yet; skipped."
TASK_HISTORY_REWRITE_COMMAND = "infrahub tasks flush flow-runs --rewrite"
# Short, because a task manager that does not answer by then would also hold the upgrade's cleanup.
TASK_HISTORY_SIZE_TIMEOUT = timedelta(seconds=10)
# Prefect's hourly cleanup deletes a smaller backlog within minutes, so the upgrade leaves it to that cleanup.
UPGRADE_CLEANUP_MIN_OLD_RUNS = 100_000
# Short, because a cleanup that already runs elsewhere finishes there without the upgrade.
UPGRADE_CLEANUP_GIVE_UP_AFTER = timedelta(minutes=2)
UPGRADE_CLEANUP_OPTION = "--no-task-history-cleanup"


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
    """Run a sample workflow through the task manager and a worker, and print its result."""
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


def run_background_services(config_file: Path, start_services: Callable[[], None]) -> None:
    """Apply the configuration's retention to Prefect's settings, then run the services until they stop, logging only Docket's warnings and errors."""
    apply_infrahub_settings_to_prefect(config_file=config_file)
    # Docket, which runs Prefect's services, logs every run of every service at INFO, about three lines a second.
    logging.getLogger("docket").setLevel(logging.WARNING)
    start_services()


@app.command()
def background_services(
    ctx: typer.Context,
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
) -> None:
    """Run the task manager's background services in the foreground, with the retention set in the configuration.

    Raises:
        typer.Exit: With code 1 when the configuration file given on the command line does not exist.

    """
    # Prefect's command-line application loads only for this command, so no other infrahub command depends on it.
    from prefect.cli.server import start_services as start_prefect_services  # noqa: PLC0415

    path = Path(config_file)
    # The default file and INFRAHUB_CONFIG may name no file, because a deployment can set every value in the environment.
    if ctx.get_parameter_source("config_file") is ParameterSource.COMMANDLINE and not path.is_file():
        print(f"Configuration file not found: {config_file}")
        raise typer.Exit(1)
    run_background_services(config_file=path, start_services=start_prefect_services)


flush_app = AsyncTyper()

app.add_typer(flush_app, name="flush")


@flush_app.callback()
def flush_callback() -> None:
    """Delete old task runs, or mark stale task runs as crashed."""


@dataclass(frozen=True)
class TaskHistoryReading:
    """What the task manager measured of its task history, or why it could not be read."""

    measured: TaskHistorySize | None
    read_error: str | None = None
    """The name of the error that kept the size from being read, when `measured` is None."""

    @property
    def line(self) -> str | None:
        """The size and the old runs, why they could not be read, or None on SQLite, where the size is not measured."""
        if self.measured is None:
            return f"Could not read the task history size from the task manager ({self.read_error})."
        if self.measured.size is None:
            return None
        taken = f"Task history takes {decimal(self.measured.size)}, with {_old_runs(measured=self.measured)} older than the retention."
        if self.measured.deletion_off_reason is not None:
            return f"{taken} Old task runs are not deleted, because {self.measured.deletion_off_reason}."
        return taken


async def read_task_history(
    client: PrefectClient, answer_within: timedelta = TASK_HISTORY_SIZE_TIMEOUT
) -> TaskHistoryReading:
    """Read the size and the old runs of the task history from the task manager, naming the error when that fails."""
    try:
        async with asyncio.timeout(answer_within.total_seconds()):
            measured = await read_task_history_size(client=client)
    # The reading only decides whether the upgrade cleans up, so a failure to read it is named and the upgrade goes on.
    except (httpx.HTTPError, ValidationError, TimeoutError) as exc:
        return TaskHistoryReading(measured=None, read_error=type(exc).__name__)
    return TaskHistoryReading(measured=measured)


def upgrade_cleanup_skip_reason(reading: TaskHistoryReading, skip: bool) -> str | None:
    """Why the upgrade does not clean up the task history, or None when it has a backlog large enough to clean up."""
    measured = reading.measured
    if skip:
        reason = f"{UPGRADE_CLEANUP_OPTION} was given"
    elif measured is None:
        reason = "the task manager did not report its task history"
    elif measured.deletion_off_reason is not None:
        return f"Task history cleanup skipped, because {measured.deletion_off_reason}"
    elif measured.old_runs < UPGRADE_CLEANUP_MIN_OLD_RUNS:
        reason = (
            f"fewer than {UPGRADE_CLEANUP_MIN_OLD_RUNS:,} runs are older than the retention, "
            "which the task manager's hourly cleanup deletes"
        )
    else:
        return None
    return f"Task history cleanup skipped, because {reason}. To get the disk space of old task history back, run: {TASK_HISTORY_REWRITE_COMMAND}"


async def clean_up_task_history_for_upgrade(
    client: PrefectClient,
    reading: TaskHistoryReading,
    skip: bool,
    console: Console,
    poll_interval: timedelta = POLL_INTERVAL,
) -> None:
    """Delete the old task history and return its disk space when the task manager measured a large backlog, or print why not.

    A cleanup that fails or cannot start is reported with the command that finishes it, and the upgrade goes on.
    """
    skipped = upgrade_cleanup_skip_reason(reading=reading, skip=skip)
    if skipped is not None:
        console.log(skipped)
        return
    console.log(
        f"Deleting the finished runs older than the task history retention, because at least "
        f"{UPGRADE_CLEANUP_MIN_OLD_RUNS:,} runs are that old, then rewriting the tables that are mostly free space"
    )
    exit_code = await flush_old_flow_runs(
        client=client,
        rewrite=True,
        console=console,
        poll_interval=poll_interval,
        give_up_after=UPGRADE_CLEANUP_GIVE_UP_AFTER,
    )
    if exit_code:
        console.log(f"The upgrade goes on without the cleanup. To finish it, run: {TASK_HISTORY_REWRITE_COMMAND}")


def _old_runs(measured: TaskHistorySize) -> str:
    if measured.old_runs_limit_reached:
        return f"more than {measured.old_runs:,} runs"
    if measured.old_runs == 0:
        return "no runs"
    return f"{measured.old_runs:,} run" if measured.old_runs == 1 else f"{measured.old_runs:,} runs"


async def flush_old_flow_runs(
    client: PrefectClient,
    rewrite: bool,
    console: Console,
    poll_interval: timedelta = POLL_INTERVAL,
    give_up_after: timedelta = GIVE_UP_AFTER,
) -> int:
    """Delete the finished runs older than the task history retention, printing the progress, waits and outcome.

    Returns:
        The exit code of the command.

    """
    try:
        cleanup = await run_task_history_cleanup(
            client=client,
            rewrite=CleanupRewrite.IF_FREED if rewrite else CleanupRewrite.NEVER,
            on_progress=lambda progress: console.log(_progress_line(cleanup=progress)),
            on_wait=lambda wait: console.log(f"Waiting to start the cleanup, because {wait.reason}"),
            poll_interval=poll_interval,
            give_up_after=give_up_after,
        )
    except TaskHistoryCleanupFailedError as exc:
        console.log(f"{ERROR_BADGE} {exc.message}")
        for line in _committed_lines(cleanup=exc.cleanup):
            console.log(line)
        return 1
    except TaskHistoryCleanupError as exc:
        console.log(f"{ERROR_BADGE} {exc.message}")
        return 1
    except httpx.HTTPError as exc:
        console.log(f"{ERROR_BADGE} {type(exc).__name__}: {exc}")
        return 1
    if cleanup is None:
        console.log(TASK_HISTORY_CLEANUP_NOT_PROVIDED)
        return 0
    for line in _summary_lines(cleanup=cleanup):
        console.log(line)
    return 0


def _runs(count: int) -> str:
    return f"{count} run" if count == 1 else f"{count} runs"


def _deleted_runs(cleanup: FollowedCleanup) -> str:
    """The runs deleted, after "at least" when they count a lost cleanup as it was last seen."""
    runs = _runs(cleanup.deleted_runs)
    return f"at least {runs}" if cleanup.counts_lost_cleanups else runs


def _progress_line(cleanup: FollowedCleanup) -> str:
    return f"Deleting the runs that ended on {cleanup.job.current_day}, {_runs(cleanup.deleted_runs)} deleted so far"


def _rewrite_lines(job: CleanupJob) -> list[str]:
    """What the rewrite did with each table it finished."""
    lines: list[str] = []
    if job.rewritten:
        lines.append(f"Rewrote {', '.join(job.rewritten)}")
    if job.mostly_live:
        lines.append(
            f"Left {', '.join(job.mostly_live)} as they are, because their live rows hold at least half of their disk space"
        )
    if job.not_rewritten:
        lines.append(f"Did not rewrite {', '.join(job.not_rewritten)}, which stayed locked by other sessions")
    if job.timed_out:
        lines.append(
            f"Did not rewrite {', '.join(job.timed_out)}, whose rewrite took longer than its time limit and was stopped"
        )
    if job.failed:
        lines.append(
            f"Did not rewrite {', '.join(job.failed)}, whose rewrite failed with a database error; "
            "the task manager log has the details"
        )
    return lines


def _committed_lines(cleanup: FollowedCleanup) -> list[str]:
    """The runs a failed cleanup and the cleanups lost before it deleted, and the tables the failed cleanup rewrote."""
    return [f"Deleted {_deleted_runs(cleanup=cleanup)} before the failure", *_rewrite_lines(job=cleanup.job)]


def _summary_lines(cleanup: FollowedCleanup) -> list[str]:
    job = cleanup.job
    lines = [
        f"Deleted {_deleted_runs(cleanup=cleanup)} that ended before {job.cutoff.astimezone(UTC):%Y-%m-%d %H:%M} UTC"
    ]
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
            "half of its disk space, to return that space to the disk. Tasks that read or write a table wait while it "
            "is rewritten, for at most a minute."
        ),
    ),
) -> None:
    """Delete the finished task runs older than the task history retention, with their logs and artifacts.

    Raises:
        typer.Exit: With code 1 when the task manager refuses or fails the cleanup.

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
