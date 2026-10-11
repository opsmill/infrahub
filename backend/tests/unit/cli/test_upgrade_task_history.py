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
COMMAND_ONLY = "To get the disk space of old task history back, run: infrahub tasks flush flow-runs --rewrite"


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
        name="size_measured",
        answer=httpx.Response(status_code=200, json={"size": 23_400_000_000}),
        expected_hint="Task history takes 23.4 GB. To get the space back, run: infrahub tasks flush flow-runs --rewrite",
    ),
    HintCase(
        name="size_not_measured_on_sqlite",
        answer=httpx.Response(status_code=200, json={"size": None}),
        expected_hint=None,
    ),
    HintCase(name="task_manager_without_the_route", answer=route_missing(), expected_hint=COMMAND_ONLY),
    HintCase(name="task_manager_unreachable", answer=unreachable(), expected_hint=COMMAND_ONLY),
    HintCase(
        name="task_manager_error",
        answer=httpx.Response(status_code=500, json={"detail": "boom"}),
        expected_hint=COMMAND_ONLY,
    ),
    HintCase(
        name="answer_without_a_size",
        answer=httpx.Response(status_code=200, json={"detail": "unexpected"}),
        expected_hint=COMMAND_ONLY,
    ),
]


@pytest.mark.usefixtures("prefect_client_without_retries")
@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in HINT_CASES])
async def test_the_hint_gives_the_size_and_the_command_or_the_command_alone(case: HintCase) -> None:
    """The hint gives the size the task manager measured, nothing on SQLite, and the command alone when it gets no size."""
    task_manager = ScriptedTaskManager(responses=[case.answer])

    async with task_manager.client() as client:
        hint = await task_history_size_hint(client=client)

    assert hint == case.expected_hint
    assert task_manager.requests == [RecordedRequest(method="GET", path=SIZE_PATH)]


async def test_the_hint_gives_the_command_alone_when_the_task_manager_answers_too_late() -> None:
    """A task manager that does not answer within the bound gets the command alone, so the upgrade goes on."""
    answered = asyncio.Event()

    async def never_answers(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/csrf-token":
            return httpx.Response(status_code=422, json={"detail": "CSRF protection is disabled."})
        await answered.wait()
        return httpx.Response(status_code=200, json={"size": 1})

    client = PrefectClient(api=TASK_MANAGER_API, httpx_settings={"transport": httpx.MockTransport(never_answers)})
    async with client:
        hint = await task_history_size_hint(client=client, answer_within=timedelta(milliseconds=50))

    assert hint == COMMAND_ONLY
