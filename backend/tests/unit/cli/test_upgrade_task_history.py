from __future__ import annotations

import ast
import asyncio
import inspect
import re
import textwrap
from dataclasses import dataclass
from datetime import timedelta

import httpx
import pytest
from prefect.client.orchestration import PrefectClient

from infrahub.cli.tasks import task_history_size_hint
from infrahub.cli.upgrade import _upgrade_execute
from tests.helpers.task_history_api import (
    SIZE_PATH,
    TASK_MANAGER_API,
    RecordedRequest,
    ScriptedTaskManager,
    route_missing,
    unreachable,
)

STEP_HEADER = re.compile(r"^\[bold\]Step (?P<number>\d+)/(?P<total>\d+): (?P<name>.+)\[/bold\]$")
COMMAND = "To get the disk space of old task history back, run: infrahub tasks flush flow-runs --rewrite"


def _without_size(error: str) -> str:
    return f"Could not read the task history size from the task manager ({error}). {COMMAND}"


def _with_size(measured: str) -> str:
    return f"{measured} To get the space back, run: infrahub tasks flush flow-runs --rewrite"


def _measured(size: int | None, old_runs: int, old_runs_limit_reached: bool) -> httpx.Response:
    return httpx.Response(
        status_code=200, json={"size": size, "old_runs": old_runs, "old_runs_limit_reached": old_runs_limit_reached}
    )


def _upgrade_outline() -> list[str]:
    """The step headers and the task history hint of the upgrade, in source order."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(_upgrade_execute)))
    outline: list[tuple[int, int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and (match := STEP_HEADER.match(node.value)):
            outline.append((node.lineno, node.col_offset, f"Step {match['number']}/{match['total']}: {match['name']}"))
        elif (
            isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "task_history_size_hint"
        ):
            outline.append((node.lineno, node.col_offset, "task_history_size_hint()"))
    return [entry for *_, entry in sorted(outline)]


def test_the_upgrade_reads_the_task_history_hint_in_the_task_manager_step() -> None:
    """The upgrade keeps its six steps, deletes no task history, and reads the hint in the task manager step."""
    assert _upgrade_outline() == [
        "Step 1/6: Database migrations",
        "Step 2/6: Internal schema",
        "Step 3/6: Core schema",
        "Step 4/6: Internal objects",
        "Step 5/6: Task manager",
        "task_history_size_hint()",
        "Step 6/6: Branch rebase",
    ]


@dataclass
class HintCase:
    name: str
    answer: httpx.Response | httpx.TransportError
    expected_hint: str | None


HINT_CASES: list[HintCase] = [
    HintCase(
        name="size_and_old_runs",
        answer=_measured(size=23_400_000_000, old_runs=1234, old_runs_limit_reached=False),
        expected_hint=_with_size("Task history takes 23.4 GB, with 1,234 runs older than the retention."),
    ),
    HintCase(
        name="one_old_run",
        answer=_measured(size=23_400_000_000, old_runs=1, old_runs_limit_reached=False),
        expected_hint=_with_size("Task history takes 23.4 GB, with 1 run older than the retention."),
    ),
    HintCase(
        name="no_old_runs",
        answer=_measured(size=1_200_000_000, old_runs=0, old_runs_limit_reached=False),
        expected_hint=_with_size("Task history takes 1.2 GB, with no runs older than the retention."),
    ),
    HintCase(
        name="old_runs_over_the_count_limit",
        answer=_measured(size=99_000_000_000, old_runs=100_000, old_runs_limit_reached=True),
        expected_hint=_with_size("Task history takes 99.0 GB, with more than 100,000 runs older than the retention."),
    ),
    HintCase(
        name="size_not_measured_on_sqlite",
        answer=_measured(size=None, old_runs=3, old_runs_limit_reached=False),
        expected_hint=None,
    ),
    HintCase(
        name="task_manager_without_the_route",
        answer=route_missing(),
        expected_hint=_without_size("PrefectHTTPStatusError"),
    ),
    HintCase(name="task_manager_unreachable", answer=unreachable(), expected_hint=_without_size("ConnectError")),
    HintCase(
        name="task_manager_error",
        answer=httpx.Response(status_code=500, json={"detail": "boom"}),
        expected_hint=_without_size("PrefectHTTPStatusError"),
    ),
    HintCase(
        name="answer_without_a_count_of_old_runs",
        answer=httpx.Response(status_code=200, json={"size": 1000}),
        expected_hint=_without_size("ValidationError"),
    ),
]


@pytest.mark.usefixtures("prefect_client_without_retries")
@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in HINT_CASES])
async def test_the_hint_gives_the_size_and_the_command_or_why_it_has_no_size(case: HintCase) -> None:
    """The hint gives the size and the old runs the task manager measured, nothing on SQLite, and why it has no size otherwise."""
    task_manager = ScriptedTaskManager(responses=[case.answer])

    async with task_manager.client() as client:
        hint = await task_history_size_hint(client=client)

    assert hint == case.expected_hint
    assert task_manager.requests == [RecordedRequest(method="GET", path=SIZE_PATH)]


async def test_the_hint_gives_the_command_without_the_size_when_the_task_manager_answers_too_late() -> None:
    """A task manager that does not answer within the bound gets the command without the size, so the upgrade goes on."""
    answered = asyncio.Event()

    async def never_answers(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/csrf-token":
            return httpx.Response(status_code=422, json={"detail": "CSRF protection is disabled."})
        await answered.wait()
        return httpx.Response(status_code=200, json={"size": 1, "old_runs": 0, "old_runs_limit_reached": False})

    client = PrefectClient(api=TASK_MANAGER_API, httpx_settings={"transport": httpx.MockTransport(never_answers)})
    async with client:
        hint = await task_history_size_hint(client=client, answer_within=timedelta(milliseconds=50))

    assert hint == _without_size("TimeoutError")
