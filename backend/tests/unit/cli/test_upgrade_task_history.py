from __future__ import annotations

import ast
import inspect
import re
import textwrap
from datetime import timedelta
from typing import TYPE_CHECKING

import typer

from infrahub.cli.upgrade import _upgrade_execute, upgrade_cmd, upgrade_task_history
from tests.helpers.task_history_api import (
    CLEANUP_PATH,
    RecordedConsole,
    RecordedRequest,
    ScriptedTaskManager,
    polled,
    route_missing,
    started,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from prefect.client.orchestration import PrefectClient

STEP_HEADER = re.compile(r"^\[bold\]Step (?P<number>\d+)/(?P<total>\d+): (?P<name>.+)\[/bold\]$")


class RecordingClientFactory:
    def __init__(self, task_manager: ScriptedTaskManager) -> None:
        self._task_manager = task_manager
        self.calls = 0

    def __call__(self) -> PrefectClient:
        self.calls += 1
        return self._task_manager.client()


def _upgrade_outline() -> list[str]:
    """The step headers and the task history cleanup calls of the upgrade, in source order."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(_upgrade_execute)))
    outline: list[tuple[int, int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and (match := STEP_HEADER.match(node.value)):
            outline.append((node.lineno, node.col_offset, f"Step {match['number']}/{match['total']}: {match['name']}"))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "upgrade_task_history":
            outline.append((node.lineno, node.col_offset, "upgrade_task_history()"))
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


def test_the_upgrade_runs_the_task_history_cleanup_as_step_six_of_seven() -> None:
    """The upgrade announces seven numbered steps and runs the task history cleanup in the one after the task manager."""
    assert _upgrade_outline() == [
        "Step 1/7: Database migrations",
        "Step 2/7: Internal schema",
        "Step 3/7: Core schema",
        "Step 4/7: Internal objects",
        "Step 5/7: Task manager",
        "Step 6/7: Task history cleanup",
        "upgrade_task_history()",
        "Step 7/7: Branch rebase",
    ]


async def test_the_step_asks_for_a_rewrite_only_when_the_deletes_free_most_of_the_tables() -> None:
    """The upgrade's cleanup asks for a rewrite only if the deletes freed more than half of the runs, then summarises."""
    task_manager = ScriptedTaskManager(
        responses=[
            started(rewrite="if_freed"),
            polled(
                rewrite="if_freed",
                state="completed",
                rewritten=True,
                current_day="2026-01-16",
                deleted_runs=40,
                size_before=3_000_000,
                size_after=1_000_000,
            ),
        ]
    )
    console = RecordedConsole()

    proceed = await upgrade_task_history(
        skip=False,
        client_factory=RecordingClientFactory(task_manager=task_manager),
        console=console.console,
        poll_interval=timedelta(0),
    )

    assert proceed is True
    assert task_manager.requests == [
        RecordedRequest(method="POST", path=CLEANUP_PATH, body={"rewrite": "if_freed"}),
        RecordedRequest(method="GET", path=f"{CLEANUP_PATH}/job-1"),
    ]
    assert console.lines == [
        "Deleted 40 runs that ended before 2026-09-04 00:00 UTC",
        "Task history tables: 3.0 MB before, 1.0 MB after",
        "Task history tables rewritten",
    ]


async def test_the_step_is_skipped_without_reaching_the_task_manager() -> None:
    """A skipped step says so and never builds a task manager client."""
    task_manager = ScriptedTaskManager(responses=[])
    client_factory = RecordingClientFactory(task_manager=task_manager)
    console = RecordedConsole()

    proceed = await upgrade_task_history(
        skip=True, client_factory=client_factory, console=console.console, poll_interval=timedelta(0)
    )

    assert proceed is True
    assert (client_factory.calls, task_manager.requests) == (0, [])
    assert console.lines == ["Task history cleanup skipped"]


async def test_a_task_manager_without_the_cleanup_lets_the_upgrade_continue() -> None:
    """A task manager that does not provide the cleanup is reported, and the upgrade continues."""
    task_manager = ScriptedTaskManager(responses=[route_missing()])
    console = RecordedConsole()

    proceed = await upgrade_task_history(
        skip=False,
        client_factory=RecordingClientFactory(task_manager=task_manager),
        console=console.console,
        poll_interval=timedelta(0),
    )

    assert proceed is True
    assert console.lines == ["The task manager does not provide the task history cleanup yet; skipped."]


async def test_a_failed_cleanup_stops_the_upgrade() -> None:
    """A cleanup that fails prints its error, and the upgrade does not go on to the next step."""
    task_manager = ScriptedTaskManager(
        responses=[
            started(rewrite="if_freed"),
            polled(
                rewrite="if_freed",
                state="failed",
                error="The cleanup failed with DBAPIError; the task manager log has the details",
            ),
        ]
    )
    console = RecordedConsole()

    proceed = await upgrade_task_history(
        skip=False,
        client_factory=RecordingClientFactory(task_manager=task_manager),
        console=console.console,
        poll_interval=timedelta(0),
    )

    assert proceed is False
    assert console.lines == ["ERROR The cleanup failed with DBAPIError; the task manager log has the details"]


def test_the_flag_that_leaves_the_cleanup_out_is_what_skips_the_step() -> None:
    """The upgrade's `--no-task-history-cleanup` flag, off by default, is passed down as the skip of the cleanup step."""
    option = inspect.signature(upgrade_cmd).parameters["no_task_history_cleanup"].default
    assert isinstance(option, typer.models.OptionInfo)
    [execute] = _calls(function=upgrade_cmd, name="_upgrade_execute")
    [step] = _calls(function=_upgrade_execute, name="upgrade_task_history")

    assert (option.param_decls, option.default) == (("--no-task-history-cleanup",), False)
    assert _keywords(call=execute)["skip_task_history_cleanup"] == "no_task_history_cleanup"
    assert _keywords(call=step)["skip"] == "skip_task_history_cleanup"
