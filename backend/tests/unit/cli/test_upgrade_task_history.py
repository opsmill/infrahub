from __future__ import annotations

import ast
import asyncio
import functools
import inspect
import re
import textwrap
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

import httpx
import pytest
import typer
from prefect.client.orchestration import PrefectClient

from infrahub.cli import tasks as tasks_module
from infrahub.cli.tasks import (
    UPGRADE_CLEANUP_GIVE_UP_AFTER,
    UPGRADE_CLEANUP_MIN_OLD_RUNS,
    TaskHistoryReading,
    clean_up_task_history_for_upgrade,
    read_task_history,
)
from infrahub.cli.upgrade import _upgrade_execute, _upgrade_task_history, upgrade_cmd
from infrahub.prefect_server.task_history_models import OLD_RUNS_COUNT_LIMIT, TaskHistorySize
from tests.helpers.task_history_api import (
    CLEANUP_PATH,
    DELETION_OFF_REASON,
    SIZE_PATH,
    TASK_MANAGER_API,
    FakeClock,
    RecordedConsole,
    RecordedRequest,
    ScriptedTaskManager,
    polled,
    route_missing,
    running_elsewhere,
    started,
    unreachable,
)

if TYPE_CHECKING:
    from collections.abc import Callable

STEP_HEADER = re.compile(r"^\[bold\]Step (?P<number>\d+)/(?P<total>\d+): (?P<name>.+)\[/bold\]$")
COMMAND = "To get the disk space of old task history back, run: infrahub tasks flush flow-runs --rewrite"
STARTED = (
    "Deleting the finished runs older than the task history retention, because at least 100,000 runs are that old, "
    "then rewriting the tables that are mostly free space"
)
RERUN = "The upgrade goes on without the cleanup. To finish it, run: infrahub tasks flush flow-runs --rewrite"


def _measured(
    size: int | None, old_runs: int, old_runs_limit_reached: bool, deletion_off_reason: str | None = None
) -> httpx.Response:
    return httpx.Response(
        status_code=200,
        json={
            "size": size,
            "old_runs": old_runs,
            "old_runs_limit_reached": old_runs_limit_reached,
            "deletion_off_reason": deletion_off_reason,
        },
    )


def _reading(old_runs: int, deletion_off_reason: str | None = None) -> TaskHistoryReading:
    return TaskHistoryReading(
        measured=TaskHistorySize(
            size=23_400_000_000,
            old_runs=old_runs,
            old_runs_limit_reached=old_runs >= OLD_RUNS_COUNT_LIMIT,
            deletion_off_reason=deletion_off_reason,
        )
    )


def _outline(function: Callable[..., object], calls: tuple[str, ...]) -> list[str]:
    """The step headers and the named calls of a function, in source order."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    outline: list[tuple[int, int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and (match := STEP_HEADER.match(node.value)):
            outline.append((node.lineno, node.col_offset, f"Step {match['number']}/{match['total']}: {match['name']}"))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in calls:
            outline.append((node.lineno, node.col_offset, f"{node.func.id}()"))
    return [entry for *_, entry in sorted(outline)]


def _calls(function: Callable[..., object], name: str) -> list[ast.Call]:
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == name
    ]


def _keywords(call: ast.Call) -> dict[str, str]:
    return {keyword.arg: ast.unparse(keyword.value) for keyword in call.keywords if keyword.arg is not None}


def test_the_upgrade_reads_the_task_history_in_the_task_manager_step_and_cleans_it_up_last() -> None:
    """The upgrade reads the task history in the task manager step and cleans it up after the branches are rebased."""
    assert _outline(function=_upgrade_execute, calls=("read_task_history", "_upgrade_task_history")) == [
        "Step 1/7: Database migrations",
        "Step 2/7: Internal schema",
        "Step 3/7: Core schema",
        "Step 4/7: Internal objects",
        "Step 5/7: Task manager",
        "read_task_history()",
        "Step 6/7: Branch rebase",
        "_upgrade_task_history()",
    ]
    assert _outline(function=_upgrade_task_history, calls=("clean_up_task_history_for_upgrade",)) == [
        "Step 7/7: Task history cleanup",
        "clean_up_task_history_for_upgrade()",
    ]


def test_the_option_that_leaves_the_cleanup_out_is_what_skips_it() -> None:
    """The upgrade's `--no-task-history-cleanup` option, off by default, is passed down as the skip of the cleanup step."""
    option = inspect.signature(upgrade_cmd).parameters["no_task_history_cleanup"].default
    assert isinstance(option, typer.models.OptionInfo)
    [execute] = _calls(function=upgrade_cmd, name="_upgrade_execute")
    [step] = _calls(function=_upgrade_execute, name="_upgrade_task_history")

    assert (option.param_decls, option.default) == (("--no-task-history-cleanup",), False)
    assert _keywords(call=execute)["skip_task_history_cleanup"] == "no_task_history_cleanup"
    assert _keywords(call=step)["skip"] == "skip_task_history_cleanup"


def test_the_cleanup_threshold_can_be_reached_by_the_count_of_old_runs() -> None:
    """The task manager stops counting old runs at its limit, so a threshold above it would never start the cleanup."""
    assert 0 < UPGRADE_CLEANUP_MIN_OLD_RUNS <= OLD_RUNS_COUNT_LIMIT


@dataclass
class ReadingCase:
    name: str
    answer: httpx.Response | httpx.TransportError
    expected_line: str | None


READING_CASES: list[ReadingCase] = [
    ReadingCase(
        name="size_and_old_runs",
        answer=_measured(size=23_400_000_000, old_runs=1234, old_runs_limit_reached=False),
        expected_line="Task history takes 23.4 GB, with 1,234 runs older than the retention.",
    ),
    ReadingCase(
        name="one_old_run",
        answer=_measured(size=23_400_000_000, old_runs=1, old_runs_limit_reached=False),
        expected_line="Task history takes 23.4 GB, with 1 run older than the retention.",
    ),
    ReadingCase(
        name="no_old_runs",
        answer=_measured(size=1_200_000_000, old_runs=0, old_runs_limit_reached=False),
        expected_line="Task history takes 1.2 GB, with no runs older than the retention.",
    ),
    ReadingCase(
        name="old_runs_over_the_count_limit",
        answer=_measured(size=99_000_000_000, old_runs=100_000, old_runs_limit_reached=True),
        expected_line="Task history takes 99.0 GB, with more than 100,000 runs older than the retention.",
    ),
    ReadingCase(
        name="old_runs_kept_by_the_vacuum_switch",
        answer=_measured(
            size=23_400_000_000, old_runs=1234, old_runs_limit_reached=False, deletion_off_reason=DELETION_OFF_REASON
        ),
        expected_line=(
            "Task history takes 23.4 GB, with 1,234 runs older than the retention. Old task runs are not deleted, "
            "because PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED does not turn on flow_runs."
        ),
    ),
    ReadingCase(
        name="size_not_measured_on_sqlite",
        answer=_measured(size=None, old_runs=3, old_runs_limit_reached=False),
        expected_line=None,
    ),
    ReadingCase(
        name="task_manager_without_the_route",
        answer=route_missing(),
        expected_line="Could not read the task history size from the task manager (PrefectHTTPStatusError).",
    ),
    ReadingCase(
        name="task_manager_unreachable",
        answer=unreachable(),
        expected_line="Could not read the task history size from the task manager (ConnectError).",
    ),
    ReadingCase(
        name="task_manager_error",
        answer=httpx.Response(status_code=500, json={"detail": "boom"}),
        expected_line="Could not read the task history size from the task manager (PrefectHTTPStatusError).",
    ),
    ReadingCase(
        name="answer_without_a_count_of_old_runs",
        answer=httpx.Response(status_code=200, json={"size": 1000}),
        expected_line="Could not read the task history size from the task manager (ValidationError).",
    ),
]


@pytest.mark.usefixtures("prefect_client_without_retries")
@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in READING_CASES])
async def test_the_reading_gives_the_size_and_the_old_runs_or_why_it_has_none(case: ReadingCase) -> None:
    """The reading gives the size and the old runs the task manager measured, nothing on SQLite, and why it has no size otherwise."""
    task_manager = ScriptedTaskManager(responses=[case.answer])

    async with task_manager.client() as client:
        reading = await read_task_history(client=client)

    assert reading.line == case.expected_line
    assert task_manager.requests == [RecordedRequest(method="GET", path=SIZE_PATH)]


async def test_the_reading_names_a_task_manager_that_answers_too_late() -> None:
    """A task manager that does not answer within the bound gives a reading without a size, so the upgrade goes on."""
    answered = asyncio.Event()

    async def never_answers(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/csrf-token":
            return httpx.Response(status_code=422, json={"detail": "CSRF protection is disabled."})
        await answered.wait()
        return httpx.Response(
            status_code=200,
            json={"size": 1, "old_runs": 0, "old_runs_limit_reached": False, "deletion_off_reason": None},
        )

    client = PrefectClient(api=TASK_MANAGER_API, httpx_settings={"transport": httpx.MockTransport(never_answers)})
    async with client:
        reading = await read_task_history(client=client, answer_within=timedelta(milliseconds=50))

    assert reading == TaskHistoryReading(measured=None, read_error="TimeoutError")
    assert reading.line == "Could not read the task history size from the task manager (TimeoutError)."


@dataclass
class SkipCase:
    name: str
    reading: TaskHistoryReading
    skip: bool
    expected_line: str


SKIP_CASES: list[SkipCase] = [
    SkipCase(
        name="option_given",
        reading=_reading(old_runs=OLD_RUNS_COUNT_LIMIT),
        skip=True,
        expected_line=f"Task history cleanup skipped, because --no-task-history-cleanup was given. {COMMAND}",
    ),
    SkipCase(
        name="fewer_old_runs_than_the_threshold",
        reading=_reading(old_runs=UPGRADE_CLEANUP_MIN_OLD_RUNS - 1),
        skip=False,
        expected_line=(
            f"Task history cleanup skipped, because fewer than {UPGRADE_CLEANUP_MIN_OLD_RUNS:,} runs are older than "
            f"the retention, which the task manager's hourly cleanup deletes. {COMMAND}"
        ),
    ),
    SkipCase(
        name="task_history_not_read",
        reading=TaskHistoryReading(measured=None, read_error="PrefectHTTPStatusError"),
        skip=False,
        expected_line=(
            f"Task history cleanup skipped, because the task manager did not report its task history. {COMMAND}"
        ),
    ),
    SkipCase(
        name="old_runs_kept_by_the_vacuum_switch",
        reading=_reading(old_runs=OLD_RUNS_COUNT_LIMIT, deletion_off_reason=DELETION_OFF_REASON),
        skip=False,
        expected_line=(
            "Task history cleanup skipped, because PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED does not turn on flow_runs"
        ),
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in SKIP_CASES])
async def test_a_skipped_cleanup_says_why_without_reaching_the_task_manager(case: SkipCase) -> None:
    """Without a large backlog the task manager can delete, the step prints why it does not clean up and sends nothing."""
    task_manager = ScriptedTaskManager(responses=[])
    console = RecordedConsole()

    async with task_manager.client() as client:
        await clean_up_task_history_for_upgrade(
            client=client, reading=case.reading, skip=case.skip, console=console.console, poll_interval=timedelta(0)
        )

    assert task_manager.requests == []
    assert console.lines == [case.expected_line]


async def test_a_large_backlog_is_deleted_and_the_mostly_free_tables_are_rewritten() -> None:
    """At the threshold the step runs the cleanup with the rewrite of the mostly free tables, then prints its summary."""
    task_manager = ScriptedTaskManager(
        responses=[
            started(rewrite="if_freed"),
            polled(
                rewrite="if_freed",
                state="completed",
                current_day="2026-08-01",
                deleted_runs=250_000,
                size_before=3_000_000_000,
                size_after=100_000_000,
                rewritten=["flow_run", "log"],
            ),
        ]
    )
    console = RecordedConsole()

    async with task_manager.client() as client:
        await clean_up_task_history_for_upgrade(
            client=client,
            reading=_reading(old_runs=UPGRADE_CLEANUP_MIN_OLD_RUNS),
            skip=False,
            console=console.console,
            poll_interval=timedelta(0),
        )

    assert task_manager.requests == [
        RecordedRequest(method="POST", path=CLEANUP_PATH, body={"rewrite": "if_freed"}),
        RecordedRequest(method="GET", path=f"{CLEANUP_PATH}/job-1"),
    ]
    assert console.lines == [
        STARTED,
        "Deleted 250000 runs that ended before 2026-09-04 00:00 UTC",
        "Task history and activity log tables: 3.0 GB before, 100.0 MB after",
        "Rewrote flow_run, log",
    ]


async def test_a_failed_cleanup_is_reported_and_the_upgrade_goes_on() -> None:
    """A cleanup that fails prints its error, what it deleted and how to finish it, without raising out of the upgrade."""
    task_manager = ScriptedTaskManager(
        responses=[
            started(rewrite="if_freed"),
            polled(
                rewrite="if_freed",
                state="failed",
                deleted_runs=40,
                error="The cleanup failed with DBAPIError; the task manager log has the details",
            ),
        ]
    )
    console = RecordedConsole()

    async with task_manager.client() as client:
        await clean_up_task_history_for_upgrade(
            client=client,
            reading=_reading(old_runs=OLD_RUNS_COUNT_LIMIT),
            skip=False,
            console=console.console,
            poll_interval=timedelta(0),
        )

    assert console.lines[0] == STARTED
    assert console.lines[2:] == ["Deleted 40 runs before the failure", RERUN]
    assert console.lines[1].endswith("The cleanup failed with DBAPIError; the task manager log has the details")


@pytest.mark.usefixtures("prefect_client_without_retries")
async def test_an_unreachable_task_manager_is_reported_and_the_upgrade_goes_on() -> None:
    """A task manager that cannot be reached for the cleanup is reported, without raising out of the upgrade."""
    task_manager = ScriptedTaskManager(responses=[unreachable()])
    console = RecordedConsole()

    async with task_manager.client() as client:
        await clean_up_task_history_for_upgrade(
            client=client,
            reading=_reading(old_runs=OLD_RUNS_COUNT_LIMIT),
            skip=False,
            console=console.console,
            poll_interval=timedelta(0),
        )

    assert console.lines == [STARTED, "ERROR ConnectError: All connection attempts failed", RERUN]


async def test_a_cleanup_that_runs_elsewhere_is_left_to_finish_there(monkeypatch: pytest.MonkeyPatch) -> None:
    """While another cleanup holds the task history, the step waits for a short time only, then leaves it and goes on."""
    clock = FakeClock()
    monkeypatch.setattr(
        tasks_module,
        "run_task_history_cleanup",
        functools.partial(tasks_module.run_task_history_cleanup, clock=clock, sleep=clock.sleep),
    )
    polls = int(UPGRADE_CLEANUP_GIVE_UP_AFTER / timedelta(seconds=30)) + 1
    task_manager = ScriptedTaskManager(responses=[running_elsewhere()] * polls)
    console = RecordedConsole()

    async with task_manager.client() as client:
        await clean_up_task_history_for_upgrade(
            client=client,
            reading=_reading(old_runs=OLD_RUNS_COUNT_LIMIT),
            skip=False,
            console=console.console,
            poll_interval=timedelta(seconds=30),
        )

    assert console.lines[:2] == [
        STARTED,
        "Waiting to start the cleanup, because the task manager answered that a cleanup runs elsewhere",
    ]
    assert console.lines[2].startswith("ERROR Gave up after 2 minutes without a cleanup to follow")
    assert console.lines[3:] == [RERUN]
    assert clock.now == UPGRADE_CLEANUP_GIVE_UP_AFTER.total_seconds()


async def test_a_task_manager_without_the_cleanup_lets_the_upgrade_go_on() -> None:
    """A task manager that reports its size but does not provide the cleanup is named, and the upgrade goes on."""
    task_manager = ScriptedTaskManager(responses=[route_missing()])
    console = RecordedConsole()

    async with task_manager.client() as client:
        await clean_up_task_history_for_upgrade(
            client=client,
            reading=_reading(old_runs=OLD_RUNS_COUNT_LIMIT),
            skip=False,
            console=console.console,
            poll_interval=timedelta(0),
        )

    assert console.lines == [STARTED, "The task manager does not provide the task history cleanup yet; skipped."]
