from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta

import httpx
import pytest
from typer.testing import CliRunner

from infrahub.cli import app
from infrahub.cli.tasks import flush_old_flow_runs
from tests.helpers.task_history_api import (
    CLEANUP_PATH,
    RecordedConsole,
    RecordedRequest,
    ScriptedTaskManager,
    polled,
    route_missing,
    running_elsewhere,
    started,
    unknown_cleanup,
    unreachable,
)

ANSI_STYLE = re.compile(r"\x1b\[[0-9;]*m")


async def _flush(task_manager: ScriptedTaskManager, console: RecordedConsole, rewrite: bool = False) -> int:
    async with task_manager.client() as client:
        return await flush_old_flow_runs(
            client=client, rewrite=rewrite, console=console.console, poll_interval=timedelta(0)
        )


@dataclass
class RewriteOptionCase:
    name: str
    rewrite: bool
    expected_body: dict[str, str]


REWRITE_OPTION_CASES: list[RewriteOptionCase] = [
    RewriteOptionCase(name="with_rewrite", rewrite=True, expected_body={"rewrite": "always"}),
    RewriteOptionCase(name="without_rewrite", rewrite=False, expected_body={"rewrite": "never"}),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in REWRITE_OPTION_CASES])
async def test_the_rewrite_option_asks_the_task_manager_to_always_rewrite(case: RewriteOptionCase) -> None:
    """The rewrite option asks for a rewrite whatever the deletes freed, and no rewrite is asked for without it."""
    mode = case.expected_body["rewrite"]
    task_manager = ScriptedTaskManager(responses=[started(rewrite=mode), polled(rewrite=mode, state="completed")])

    exit_code = await _flush(task_manager=task_manager, console=RecordedConsole(), rewrite=case.rewrite)

    assert exit_code == 0
    assert task_manager.requests[0] == RecordedRequest(method="POST", path=CLEANUP_PATH, body=case.expected_body)


async def test_the_rewrite_option_follows_a_cleanup_already_running_to_its_own_summary() -> None:
    """With the rewrite option, a cleanup already running is reported from the progress it had when joined to its end."""
    task_manager = ScriptedTaskManager(
        responses=[
            started(rewrite="always", current_day="2026-01-15", deleted_runs=7),
            polled(
                rewrite="always",
                state="completed",
                rewritten=True,
                current_day="2026-01-15",
                deleted_runs=7,
                size_before=3_000_000,
                size_after=1_000_000,
            ),
        ]
    )
    console = RecordedConsole()

    exit_code = await _flush(task_manager=task_manager, console=console, rewrite=True)

    assert exit_code == 0
    assert task_manager.requests == [
        RecordedRequest(method="POST", path=CLEANUP_PATH, body={"rewrite": "always"}),
        RecordedRequest(method="GET", path=f"{CLEANUP_PATH}/job-1"),
    ]
    assert console.lines == [
        "Deleting the runs that ended on 2026-01-15, 7 runs deleted so far",
        "Deleted 7 runs that ended before 2026-09-04 00:00 UTC",
        "Task history tables: 3.0 MB before, 1.0 MB after",
        "Task history tables rewritten",
    ]


async def test_progress_lines_then_the_summary_are_printed() -> None:
    """Each change of progress prints a line, then the outcome is summarised with the sizes the task manager measured."""
    task_manager = ScriptedTaskManager(
        responses=[
            started(rewrite="always"),
            polled(rewrite="always", current_day="2026-01-15", deleted_runs=1),
            polled(rewrite="always", current_day="2026-01-16", deleted_runs=1200),
            polled(
                rewrite="always",
                state="completed",
                rewritten=True,
                current_day="2026-01-16",
                deleted_runs=1234,
                size_before=25_300_000_000,
                size_after=1_200_000_000,
                not_rewritten=["log", "artifact"],
            ),
        ]
    )
    console = RecordedConsole()

    exit_code = await _flush(task_manager=task_manager, console=console, rewrite=True)

    assert exit_code == 0
    assert console.lines == [
        "Deleting the runs that ended on 2026-01-15, 1 run deleted so far",
        "Deleting the runs that ended on 2026-01-16, 1200 runs deleted so far",
        "Deleted 1234 runs that ended before 2026-09-04 00:00 UTC",
        "Task history tables: 25.3 GB before, 1.2 GB after",
        "Task history tables rewritten, except log, artifact, which stayed locked",
    ]


async def test_a_cleanup_that_rewrote_nothing_on_a_database_without_sizes_says_so() -> None:
    """Without sizes from the task manager the summary leaves them out, and says the tables were not rewritten."""
    task_manager = ScriptedTaskManager(responses=[running_elsewhere(), started(), polled(state="completed")])
    console = RecordedConsole()

    exit_code = await _flush(task_manager=task_manager, console=console)

    assert exit_code == 0
    assert console.lines == [
        "Waiting to start the cleanup, because the task manager answered that a cleanup runs elsewhere",
        "Deleted 0 runs that ended before 2026-09-04 00:00 UTC",
        "Task history tables not rewritten",
    ]


@pytest.mark.usefixtures("prefect_client_without_retries")
async def test_each_wait_prints_one_line_when_it_starts_or_its_reason_changes() -> None:
    """A wait prints its reason once, however many times the start is posted again, and again when the reason changes."""
    task_manager = ScriptedTaskManager(
        responses=[
            running_elsewhere(),
            running_elsewhere(),
            started(),
            unknown_cleanup(),
            started(id="job-2"),
            unreachable(),
            unreachable(),
            started(id="job-3"),
            polled(id="job-3", state="completed"),
        ]
    )
    console = RecordedConsole()

    exit_code = await _flush(task_manager=task_manager, console=console)

    assert exit_code == 0
    assert console.lines == [
        "Waiting to start the cleanup, because the task manager answered that a cleanup runs elsewhere",
        "Waiting to start the cleanup, because the task manager answered that it does not know the cleanup",
        "Waiting to start the cleanup, because the task manager could not be reached",
        "Deleted 0 runs that ended before 2026-09-04 00:00 UTC",
        "Task history tables not rewritten",
    ]


async def test_a_task_manager_without_the_cleanup_skips_it_and_succeeds() -> None:
    """A task manager that does not provide the cleanup is reported, and the command still succeeds."""
    task_manager = ScriptedTaskManager(responses=[route_missing()])
    console = RecordedConsole()

    exit_code = await _flush(task_manager=task_manager, console=console, rewrite=True)

    assert exit_code == 0
    assert console.lines == ["The task manager does not provide the task history cleanup yet; skipped."]


async def test_a_failed_cleanup_prints_its_error_and_fails() -> None:
    """A cleanup that fails in the task manager prints the error it recorded and exits with code 1."""
    task_manager = ScriptedTaskManager(
        responses=[
            started(),
            polled(current_day="2026-01-15", deleted_runs=7),
            polled(
                state="failed",
                current_day="2026-01-15",
                deleted_runs=7,
                error="The cleanup failed with DBAPIError; the task manager log has the details",
            ),
        ]
    )
    console = RecordedConsole()

    exit_code = await _flush(task_manager=task_manager, console=console)

    assert exit_code == 1
    assert console.lines == [
        "Deleting the runs that ended on 2026-01-15, 7 runs deleted so far",
        "ERROR The cleanup failed with DBAPIError; the task manager log has the details",
        "Deleted 7 runs before the failure",
    ]


@dataclass
class FailedAfterRewriteCase:
    name: str
    deleted_runs: int
    not_rewritten: list[str]
    expected_committed: str


FAILED_AFTER_REWRITE_CASES: list[FailedAfterRewriteCase] = [
    FailedAfterRewriteCase(
        name="every_table_rewritten",
        deleted_runs=1,
        not_rewritten=[],
        expected_committed="Deleted 1 run before the failure; task history tables rewritten",
    ),
    FailedAfterRewriteCase(
        name="tables_left_locked",
        deleted_runs=40,
        not_rewritten=["log", "artifact"],
        expected_committed=(
            "Deleted 40 runs before the failure; task history tables rewritten, except log, artifact, which stayed locked"
        ),
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in FAILED_AFTER_REWRITE_CASES])
async def test_a_cleanup_that_failed_after_its_rewrite_prints_what_it_deleted_and_rewrote(
    case: FailedAfterRewriteCase,
) -> None:
    """A cleanup that failed once its rewrite had run prints the runs it deleted and the tables it rewrote."""
    task_manager = ScriptedTaskManager(
        responses=[
            started(rewrite="always"),
            polled(
                rewrite="always",
                state="failed",
                rewritten=True,
                deleted_runs=case.deleted_runs,
                not_rewritten=case.not_rewritten,
                size_before=1000,
                error="The cleanup failed with DBAPIError; the task manager log has the details",
            ),
        ]
    )
    console = RecordedConsole()

    exit_code = await _flush(task_manager=task_manager, console=console, rewrite=True)

    assert exit_code == 1
    assert console.lines == [
        "ERROR The cleanup failed with DBAPIError; the task manager log has the details",
        case.expected_committed,
    ]


async def test_an_unreachable_task_manager_prints_the_error_and_fails() -> None:
    """A task manager that cannot be reached prints the transport error on one line and exits with code 1."""
    task_manager = ScriptedTaskManager(responses=[unreachable()])
    console = RecordedConsole()

    exit_code = await _flush(task_manager=task_manager, console=console, rewrite=True)

    assert exit_code == 1
    assert task_manager.requests == [RecordedRequest(method="POST", path=CLEANUP_PATH, body={"rewrite": "always"})]
    assert console.lines == ["ERROR ConnectError: All connection attempts failed"]


async def test_an_unexpected_answer_prints_the_error_and_fails() -> None:
    """An error answer other than the ones the cleanup expects prints the error and exits with code 1."""
    task_manager = ScriptedTaskManager(responses=[httpx.Response(status_code=500, json={"detail": "boom"})])
    console = RecordedConsole()

    exit_code = await _flush(task_manager=task_manager, console=console)

    assert exit_code == 1
    assert console.lines == [
        "ERROR PrefectHTTPStatusError: Server error '500 Internal Server Error' for url "
        "'http://task-manager:4200/api/infrahub/task-history/cleanup' - Response: {'detail': 'boom'} - "
        "For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/500"
    ]


@dataclass
class RemovedOptionCase:
    name: str
    option: str


REMOVED_OPTION_CASES: list[RemovedOptionCase] = [
    RemovedOptionCase(name="days_to_keep", option="--days-to-keep"),
    RemovedOptionCase(name="batch_size", option="--batch-size"),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in REMOVED_OPTION_CASES])
def test_the_number_of_days_and_the_batch_size_are_no_longer_options(case: RemovedOptionCase) -> None:
    """The command reads the retention from the task manager, so it refuses a number of days or a batch size."""
    result = CliRunner().invoke(app, ["tasks", "flush", "flow-runs", case.option, "30"], env={"COLUMNS": "200"})

    errors = [line.strip("│ ") for line in ANSI_STYLE.sub("", result.output).splitlines() if "No such option" in line]
    assert (result.exit_code, errors) == (2, [f"No such option '{case.option}'."])
